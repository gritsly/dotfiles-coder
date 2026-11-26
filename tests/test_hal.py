import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'dotfiles.codespaces/skills/hal/scripts/hal.py'
spec = importlib.util.spec_from_file_location('hal', SCRIPT)
hal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hal)

DAY = 24 * 60 * 60
WEEK = 7 * DAY
NOW = 1_000_000_000


def fixed(route, short=0, week=0, days_to_reset=7, resets=0, expiry=float('inf')):
    """A quota with fixed usage, read at NOW."""
    base = hal.Claude if route == 'claude' else hal.Codex

    class Fixed(base):
        def read_usage(self):
            self.set_usage(short, NOW + 3600, week, NOW + days_to_reset * DAY, WEEK, resets, expiry, NOW)
    return Fixed(route)


class PaceTest(unittest.TestCase):
    def test_pace_line(self):
        self.assertAlmostEqual(fixed('claude').weekly_pace, 12.5)
        self.assertAlmostEqual(fixed('claude', days_to_reset=3.5).weekly_pace, 56.25)
        self.assertEqual(fixed('claude', days_to_reset=0).weekly_pace, 100)

    def test_above_pace_reopens_when_line_reaches_use(self):
        available, _, opens = fixed('codex', week=60, days_to_reset=4).gate('work')
        self.assertFalse(available)
        self.assertAlmostEqual(opens, NOW + 4 * DAY - 8 * DAY * 0.4)

    def test_claude_keeps_coordinator_room(self):
        self.assertTrue(fixed('claude', short=80).gate('work')[0])
        available, note, opens = fixed('claude', short=81).gate('work')
        self.assertFalse(available)
        self.assertIn('> 80%', note)
        self.assertEqual(opens, NOW + 3600)
        self.assertTrue(fixed('claude', short=90).gate('review')[0])
        self.assertFalse(fixed('claude', short=91).gate('review')[0])

    def test_codex_keeps_room_for_reviews(self):
        self.assertFalse(fixed('codex', short=61).gate('work')[0])
        self.assertTrue(fixed('codex', short=99).gate('review')[0])

    def test_exhausted_week_opens_at_reset(self):
        available, _, opens = fixed('codex', week=100, days_to_reset=2).gate('work')
        self.assertFalse(available)
        self.assertEqual(opens, NOW + 2 * DAY)

    def test_read_error_blocks_without_opening(self):
        class Broken(hal.Claude):
            def read_usage(self):
                raise RuntimeError('no token')
        self.assertEqual(Broken('claude').gate('work'), (False, 'claude unavailable: no token', None))


class RushTest(unittest.TestCase):
    def test_rush_needs_enough_resets(self):
        self.assertTrue(fixed('claude', week=20, days_to_reset=6, resets=1).rush)
        self.assertFalse(fixed('codex', week=20, days_to_reset=6, resets=1).rush)
        self.assertTrue(fixed('codex', week=20, days_to_reset=6, resets=2).rush)

    def test_rush_needs_lead_before_refresh(self):
        # 2x pace burns 80 % in 2.8 days: too late for a refresh in 3 days.
        self.assertFalse(fixed('claude', week=20, days_to_reset=3, resets=1).rush)

    def test_rush_needs_exhaustion_before_expiry(self):
        self.assertFalse(fixed('claude', week=20, days_to_reset=6, resets=1, expiry=NOW + DAY).rush)

    def test_rush_skips_pace_and_allows_reset(self):
        quota = fixed('claude', week=100, days_to_reset=6, resets=1)
        self.assertTrue(quota.rush)
        self.assertTrue(quota.gate('work')[0])
        self.assertFalse(quota.gate('work', allow_reset=False)[0])

    def test_rush_keeps_coordinator_room(self):
        self.assertFalse(fixed('claude', short=81, week=20, days_to_reset=6, resets=1).gate('work')[0])


class RoutingTest(unittest.TestCase):
    def test_claude_first_then_codex_even_in_rush(self):
        self.assertEqual(hal.candidates('implement', 'normal', False, None, None),
                         [('claude', hal.OPUS, 'high'), ('codex', hal.SOL, 'high')])
        self.assertEqual(hal.candidates('research', 'small', False, 'codex', None),
                         [('codex', hal.SOL, 'medium'), ('claude', hal.OPUS, 'medium')])
        self.assertEqual(hal.candidates('implement', 'complex', False, None, None),
                         [('claude', hal.FABLE, 'medium'), ('codex', hal.SOL, 'xhigh')])

    def test_plan_runs_one_step_above_work(self):
        plans = {size: hal.candidates('plan', size, False, None, None) for size in ('small', 'normal', 'complex')}
        self.assertEqual(plans['small'], [('claude', hal.OPUS, 'high'), ('codex', hal.SOL, 'high')])
        self.assertEqual(plans['normal'], [('claude', hal.FABLE, 'medium'), ('codex', hal.SOL, 'xhigh')])
        self.assertEqual(plans['complex'], [('claude', hal.FABLE, 'high'), ('codex', hal.ASTRA, 'medium')])

    def test_security_uses_mythos_in_place_of_fable(self):
        work = [hal.candidates('implement', size, True, None, None)[0][1:] for size in ('small', 'normal', 'complex')]
        self.assertEqual(work, [(hal.OPUS, 'medium'), (hal.OPUS, 'high'), (hal.MYTHOS, 'medium')])
        plan = [hal.candidates('plan', size, True, None, None)[0][1:] for size in ('small', 'normal', 'complex')]
        self.assertEqual(plan, [(hal.OPUS, 'high'), (hal.MYTHOS, 'medium'), (hal.MYTHOS, 'high')])
        self.assertEqual(hal.candidates('plan', 'complex', True, None, None)[1], ('codex', hal.ASTRA, 'medium'))

    def test_codex_reviewer_matches_strength(self):
        cases = {'claude-sonnet-5-5:high': (hal.SOL, 'medium'), 'claude-opus-5-5:medium': (hal.SOL, 'medium'),
                 'claude-opus-5-5:high': (hal.SOL, 'high'), 'claude-opus-5-5:max': (hal.SOL, 'high'),
                 'claude-fable-5-2:low': (hal.SOL, 'high'), 'claude-fable-5-2:medium': (hal.SOL, 'xhigh'),
                 'claude-fable-5-2:high': (hal.ASTRA, 'medium'), 'claude-mythos-5-2:high': (hal.ASTRA, 'medium')}
        for review_of, peer in cases.items():
            routes = hal.candidates('review', 'normal', False, None, review_of)
            self.assertEqual(routes[0], ('codex', *peer), review_of)
            self.assertEqual(routes[1], ('claude', *review_of.split(':')))

    def test_claude_reviews_codex_work(self):
        self.assertEqual(hal.candidates('review', 'normal', False, None, 'gpt-6.2-sol:high')[0],
                         ('claude', hal.OPUS, 'high'))
        self.assertEqual(hal.candidates('review', 'normal', False, None, 'gpt-6.2-sol:xhigh')[0],
                         ('claude', hal.FABLE, 'medium'))
        self.assertEqual(hal.candidates('review', 'normal', False, None, 'gpt-6.2-astra:medium')[0],
                         ('claude', hal.FABLE, 'high'))

    def test_launch_options(self):
        self.assertEqual(hal.launch_options('claude', hal.OPUS, 'medium', []),
                         (['--agent', 'claude', '--model', hal.OPUS, '--effort', 'medium'], hal.OPUS, 'medium'))
        self.assertEqual(hal.launch_options('codex', hal.SOL, 'high', ['--model', 'x', '--effort', 'low']),
                         (['--agent', 'codex'], 'x', 'low'))


if __name__ == '__main__':
    unittest.main()
