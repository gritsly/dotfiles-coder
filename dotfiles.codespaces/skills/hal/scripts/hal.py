#!/usr/bin/env python3
"""HAL router: start Orca workers on Claude or Codex from live quota data.

  hal.py start --role plan|implement|research|review [--size small|normal|complex]
               [--security] [--prefer claude|codex] [--review-of MODEL:EFFORT]
               [--route claude|codex] -- <worker-start options without --agent>
  hal.py status    Print the availability of each route.

Claude does the work and Codex takes over when Claude is off. A review goes to a
Codex or Claude model of similar strength in the other family first. Exit codes:
Orca's worker-start code after a start, 3 when no route is available.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

# 5h start limits in percent. Claude keeps room for the coordinator; both keep room to review the other.
START_LIMIT_5H = {'claude': {'work': 80, 'review': 90}, 'codex': {'work': 60, 'review': 99}}
# The pace line starts 24h ahead and reaches 100 % at the weekly refresh.
WEEKLY_HEAD_START_SECONDS = 24 * 60 * 60
# Rush needs min_resets banked resets and a 2x pace forecast that reaches 100 %
# at least 60h before the refresh and before the first reset expires.
MIN_RESET_LEAD_SECONDS = 60 * 60 * 60
RUSH_PACE_MULTIPLIER = 2
SONNET, OPUS, FABLE, MYTHOS = 'claude-sonnet-5-5', 'claude-opus-5-5', 'claude-fable-5-2', 'claude-mythos-5-2'
SOL, ASTRA = 'gpt-6.2-sol', 'gpt-6.2-astra'
CLAUDE_RANK = {SONNET: 0, OPUS: 1, FABLE: 2, MYTHOS: 3}
EFFORTS = {'low': 0, 'medium': 1, 'high': 2, 'xhigh': 3, 'max': 4, 'ultra': 5}
WORK_MODELS = {'small': (SONNET, 'high'), 'normal': (OPUS, 'medium'), 'complex': (OPUS, 'high')}
ROUTES = ['claude', 'codex']
ORCA = os.environ.get('ORCA_CLI_COMMAND') or 'orca'
CLAUDE_API = os.environ.get('HAL_CLAUDE_API') or 'https://api.anthropic.com'
CLAUDE_DIR = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')


def clock(epoch):
    fmt = '%H:%M' if time.strftime('%F', time.localtime(epoch)) == time.strftime('%F') else '%a %H:%M'
    return time.strftime(fmt, time.localtime(epoch))


def epoch(iso):
    return datetime.fromisoformat(iso).timestamp() if iso else None


def codex_request(method, params=None):
    """Send one request to `codex app-server` with the current CODEX_HOME."""
    process = subprocess.Popen(['codex', 'app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
    timer = threading.Timer(45, process.kill)
    timer.start()
    reply = None
    request = {'id': 2, 'method': method}
    if params is not None:
        request['params'] = params
    try:
        for message in ({'id': 1, 'method': 'initialize',
                         'params': {'clientInfo': {'name': 'hal', 'version': '1'}}},
                        {'method': 'initialized'}, request):
            process.stdin.write(json.dumps(message) + '\n')
        process.stdin.flush()
        for line in process.stdout:
            message = json.loads(line)
            if message.get('id') == 2:
                reply = message
                break
    finally:
        timer.cancel()
        process.kill()
        process.wait()
    if reply is None or 'error' in reply:
        raise RuntimeError(f'{method} failed')
    return reply['result']


def claude_request(path, body=None):
    """Call the Claude subscription API with Claude Code's OAuth token. HAL never refreshes it.

    The server reports banked resets only to Claude Code, so the request uses its User-Agent."""
    token = json.loads((CLAUDE_DIR / '.credentials.json').read_text())['claudeAiOauth']['accessToken']
    version = subprocess.run(['claude', '--version'], capture_output=True, text=True,
                             check=True).stdout.split()[0]
    request = urllib.request.Request(
        CLAUDE_API + path, data=None if body is None else json.dumps(body).encode(),
        headers={'Authorization': f'Bearer {token}', 'anthropic-beta': 'oauth-2025-04-20',
                 'Content-Type': 'application/json', 'User-Agent': f'claude-cli/{version} (external, cli)'})
    with urllib.request.urlopen(request, timeout=30) as reply:
        return json.loads(reply.read())


QUOTA_ERRORS = (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError)


class Quota:
    """Live usage of one subscription and its start rules."""
    min_resets = 2
    ordinary_usage_allowed = None

    def __init__(self, route):
        self.route = route
        self.error = None
        self.rush = False
        try:
            self.read_usage()
        except QUOTA_ERRORS as error:
            self.error = f'{route} unavailable: {error}'

    def set_usage(self, short_used, short_resets, week_used, week_resets, span, resets, reset_expiry,
                  now=None):
        now = time.time() if now is None else now
        self.short_used, self.short_resets = short_used, short_resets
        self.week_used, self.week_resets = week_used, week_resets
        self.banked_resets = resets
        elapsed = span - (week_resets - now)
        self.pace_span = span + WEEKLY_HEAD_START_SECONDS
        self.weekly_pace = min(100, 100 * (elapsed + WEEKLY_HEAD_START_SECONDS) / self.pace_span)
        exhausted_at = now + span * max(0, 100 - week_used) / (100 * RUSH_PACE_MULTIPLIER)
        self.rush = (resets >= self.min_resets and exhausted_at <= week_resets - MIN_RESET_LEAD_SECONDS
                     and exhausted_at <= reset_expiry)

    def gate(self, kind, *, allow_reset=True):
        """Return (available, note, opens) for a 'work' or 'review' start; opens is when all blocks pass."""
        if self.error:
            return False, self.error, None
        short, week, limit = self.short_used, self.week_used, START_LIMIT_5H[self.route][kind]
        blocks = []
        if short > limit:
            blocks.append((self.short_resets, f'5h {short:g}% > {limit}%, reopens {clock(self.short_resets)}'))
        if week >= 100 and not (allow_reset and self.rush):
            blocks.append((self.week_resets, f'week {week:g}% exhausted, resets {clock(self.week_resets)}'))
        elif week < 100 and week > self.weekly_pace and not self.rush:
            reopens = self.week_resets - self.pace_span * (1 - week / 100)
            blocks.append((reopens, f'week {week:g}% > pace {self.weekly_pace:.1f}%, reopens {clock(reopens)}'))
        if blocks:
            return False, f'{self.route} ' + '; '.join(note for _, note in blocks), max(t for t, _ in blocks)
        if week >= 100:
            return True, f'{self.route} week {week:g}% exhausted, banked reset available', None
        pace = f'pace {self.weekly_pace:.1f}%'
        if self.rush:
            pace = f'rush ({self.banked_resets} banked resets, 2x pace forecast)'
        return True, f'{self.route} 5h {short:g}%, week {week:g}%, {pace}', None

    def redeem_week(self, kind):
        """Use one banked reset on an exhausted week, then check the gate again."""
        try:
            self.read_usage()
        except QUOTA_ERRORS:
            return False, f'{self.route} could not refresh usage before banked reset', None
        available, note, opens = self.gate(kind)
        if not available or self.week_used < 100:
            return available, note, opens

        # Starts for the same account and exhausted week share one logical reset attempt.
        attempt = f'hal:weekly-reset:{self.account}:{self.week_resets}'
        try:
            confirmed = self.consume_reset(str(uuid.uuid5(uuid.NAMESPACE_URL, attempt)))
        except QUOTA_ERRORS:
            confirmed = False

        try:
            self.read_usage()
        except QUOTA_ERRORS:
            return False, f'{self.route} could not verify usage after banked reset attempt', None
        available, note, opens = self.gate(kind, allow_reset=False)
        if not available or self.ordinary_usage_allowed is False:
            return False, f'{self.route} usage unavailable after banked reset attempt ({note})', opens
        reset_note = 'banked reset confirmed' if confirmed else 'usage available after reset attempt'
        return True, f'{note}, {reset_note}', None


class Codex(Quota):
    min_resets = 2  # keep one reset for an emergency

    def read_usage(self):
        usage = codex_request('account/rateLimits/read')
        limits = usage['rateLimits']
        windows = sorted((w for w in (limits.get('primary'), limits.get('secondary')) if w),
                         key=lambda w: w['windowDurationMins'])
        if len(windows) != 2:
            raise RuntimeError('rate-limit windows missing')
        short, week = windows
        self.ordinary_usage_allowed = usage.get('ordinaryUsageAllowed')
        self.account = usage.get('accountId') or self.route
        credits = usage.get('rateLimitResetCredits') or {}
        expiries = [c['expiresAt'] for c in credits.get('credits') or []
                    if c.get('status') == 'available' and c.get('expiresAt')]
        self.set_usage(short['usedPercent'], short['resetsAt'], week['usedPercent'], week['resetsAt'],
                       week['windowDurationMins'] * 60, credits.get('availableCount', 0),
                       min(expiries, default=float('inf')))

    def consume_reset(self, key):
        result = codex_request('account/rateLimitResetCredit/consume', {'idempotencyKey': key})
        return result.get('outcome') in ('reset', 'alreadyRedeemed')


class Claude(Quota):
    min_resets = 1  # grants expire, so keep none back

    def read_usage(self):
        path = '/api/oauth/usage?cedar_ember=1&skip_spend=1'
        try:
            usage = claude_request(path)
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise
            # Expired token: Claude Code's /usage refreshes it under its own lock, with no model request.
            subprocess.run(['claude', '-p', '/usage', '--no-session-persistence', '--setting-sources', '',
                            '--output-format', 'json'], capture_output=True, timeout=60, check=True)
            usage = claude_request(path)
        short, week = usage['five_hour'], usage['seven_day']
        program = usage.get('cedar_ember') or {}
        self.grant = program.get('next_grant_id')
        grant = next((g for g in program.get('grants') or [] if g.get('id') == self.grant), None)
        usable = (program.get('eligible') and (epoch(program.get('cooldown_until')) or 0) <= time.time() and grant
                  and grant.get('usable_now') and not grant.get('paused')
                  and 'seven_day' in grant.get('clears', []))
        self.account = json.loads((CLAUDE_DIR / '.claude.json').read_text())['oauthAccount']['organizationUuid']
        self.set_usage(short['utilization'], epoch(short['resets_at']), week['utilization'],
                       epoch(week['resets_at']), 7 * 24 * 60 * 60,
                       grant['resets_left'] if usable else 0,
                       (epoch(grant['ends_at']) if usable else None) or float('inf'))

    def consume_reset(self, key):
        result = claude_request(f'/api/organizations/{self.account}/reset_rate_limits',
                                {'program': 'cedar_ember', 'grant_id': self.grant, 'request_id': key})
        return result.get('result') == 'reset'


def load(routes):
    return {route: Claude(route) if route == 'claude' else Codex(route) for route in dict.fromkeys(routes)}


def level(model, effort):
    return CLAUDE_RANK.get(model, CLAUDE_RANK[OPUS]), EFFORTS.get(effort, EFFORTS['medium'])


def codex_peer(model, effort):
    """Codex model of similar strength. Astra stops at medium effort to save the Codex limits."""
    if level(model, effort) <= level(OPUS, 'medium'):
        return SOL, 'medium'
    if level(model, effort) < level(FABLE, 'medium'):
        return SOL, 'high'
    return ASTRA, 'medium'


def claude_peer(model, effort):
    """Claude model of similar strength for Codex work."""
    if 'astra' in model:
        return FABLE, 'medium'
    return OPUS, 'high' if EFFORTS.get(effort, 1) >= EFFORTS['high'] else 'medium'


def work_model(role, size, security):
    """Fable plans; Mythos plans security work; Opus is the default worker; Sonnet takes small tasks."""
    if role == 'plan':
        return MYTHOS if security else FABLE, 'high' if size == 'complex' else 'medium'
    return WORK_MODELS[size]


def candidates(role, size, security, prefer, review_of):
    """Return (route, model, effort) in start order."""
    if role == 'review':
        model, _, effort = review_of.partition(':')
        effort = effort or 'medium'
        if model.startswith('claude-'):
            return [('codex', *codex_peer(model, effort)), ('claude', model, effort)]
        return [('claude', *claude_peer(model, effort)), ('codex', model, effort)]
    model, effort = work_model(role, size, security)
    order = [('claude', model, effort), ('codex', *codex_peer(model, effort))]
    return order[::-1] if prefer == 'codex' else order


def launch_options(route, model, effort, given):
    """Return the agent options and the model and effort the worker gets."""
    if '--model' in given:
        model, effort = given[given.index('--model') + 1], 'medium'
    if '--effort' in given:
        effort = given[given.index('--effort') + 1]
    options = ['--agent', route]
    if '--model' not in given:
        options += ['--model', model]
        if '--effort' not in given:
            options += ['--effort', effort]
    return options, model, effort


def start(args, given):
    if '--agent' in given or '--terminal' in given:
        sys.exit('hal: the router chooses the agent; remove --agent or --terminal')
    if args.role == 'review' and not args.review_of:
        sys.exit('hal: a review needs --review-of MODEL:EFFORT from the implementer\'s first output line')
    if args.security and args.role != 'plan':
        sys.exit('hal: --security applies to --role plan; Sonnet and Opus cover security in other tasks')
    routes = candidates(args.role, args.size, args.security, args.prefer, args.review_of)
    if args.route:
        routes = [r for r in routes if r[0] == args.route]
    quota = load(route for route, _, _ in routes)
    kind = 'review' if args.role == 'review' else 'work'
    skipped, openings = [], []
    for route, model, effort in routes:
        available, note, opens = quota[route].gate(kind)
        if available and quota[route].week_used >= 100:
            available, note, opens = quota[route].redeem_week(kind)
        if not available:
            skipped.append(note)
            openings += [opens] if opens else []
            continue
        options, model, effort = launch_options(route, model, effort, given)
        hint = f' (review with --review-of {model}:{effort})' if kind == 'work' else ''
        print(f'hal: {model}:{effort} on {route}{hint}; {note}'
              + (f"; skipped: {'; '.join(skipped)}" if skipped else ''), flush=True)
        command = [ORCA, 'orchestration', 'worker-start', *options, *given]
        os.execvp(command[0], command)
    print(f"hal: no route available; {'; '.join(skipped)}")
    if openings:
        print('hal: next opening ' + datetime.fromtimestamp(min(openings)).astimezone().isoformat(timespec='seconds'))
    sys.exit(3)


def status():
    quota = load(ROUTES)
    for route in ROUTES:
        gates = {kind: quota[route].gate(kind) for kind in ('work', 'review')}
        notes = dict.fromkeys(note for _, note, _ in gates.values())
        print(', '.join(f"{kind} {'ok' if gate[0] else 'off'}" for kind, gate in gates.items())
              + ': ' + '; '.join(notes))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    begin = commands.add_parser('start')
    begin.add_argument('--role', choices=['plan', 'implement', 'research', 'review'], required=True)
    begin.add_argument('--size', choices=['small', 'normal', 'complex'], default='normal')
    begin.add_argument('--security', action='store_true')
    begin.add_argument('--prefer', choices=ROUTES)
    begin.add_argument('--review-of', metavar='MODEL:EFFORT')
    begin.add_argument('--route', choices=ROUTES)
    begin.add_argument('given', nargs=argparse.REMAINDER)
    commands.add_parser('status')
    args = parser.parse_args()

    if args.command == 'start':
        start(args, args.given[1:] if args.given[:1] == ['--'] else args.given)
    else:
        status()


if __name__ == '__main__':
    main()
