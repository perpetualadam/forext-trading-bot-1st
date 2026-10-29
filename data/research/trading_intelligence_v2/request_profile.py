"""Fixed request selection only; no authority, credentials, files or network.

Selection is process-local, captured once before admission imports. A child gets
the same fixed selector on its command line, never an arbitrary endpoint/spec.
"""
import sys

PILOT_IDS = ('109f365402a844adacad671d62e4458f',
             'b2e5582e3cd347bd80a02109d7a476c2',
             '5d4e7676ab9e4393a4678cfb23274a4c')
WINDOWS = (('2024-08-05T00:00:00+00:00', '2024-08-08T11:19:59+00:00'),
           ('2024-08-08T11:20:00+00:00', '2024-08-11T22:39:59+00:00'),
           ('2024-08-11T22:40:00+00:00', '2024-08-11T23:59:59+00:00'))
FLAGS = tuple('--pilot-window=' + str(i) for i in (1, 2, 3))


def _selection(argv):
    candidates = [x for x in argv if x.startswith('--pilot-window')]
    if not candidates:
        return None
    if len(candidates) != 1 or candidates[0] not in FLAGS:
        raise ValueError('FIXED_PILOT_SELECTOR_REQUIRED')
    return FLAGS.index(candidates[0])


SELECTED = _selection(sys.argv[1:])


def arguments():
    return [] if SELECTED is None else [FLAGS[SELECTED]]


def request_id():
    return None if SELECTED is None else PILOT_IDS[SELECTED]


def specification(index=None):
    begin, end = (('2026-09-02T10:00:00Z', '2026-09-02T10:49:59Z')
                  if index is None else WINDOWS[index])
    return dict(method='GET', host='api-fxtrade.oanda.com',
                path='/v3/instruments/EUR_USD/candles',
                params={'from': begin, 'to': end, 'granularity': 'M5',
                        'price': 'MBA', 'smooth': 'false', 'includeFirst': 'true'})


def active_specification():
    return specification(SELECTED)
