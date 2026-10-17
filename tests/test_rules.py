from datetime import date

from review_campaign_agent.models import Campaign, Status
from review_campaign_agent.rules import plan_notifications

TODAY = date(2026, 10, 17)


def selected(deadline=None, notified=None, status=Status.SELECTED):
    return Campaign("s", "1", "title", status, review_deadline=deadline, notified=set(notified or ()))


def kinds(campaigns, today=TODAY):
    return [n.kind for n in plan_notifications(campaigns, today)]


def test_new_selection_notified_once():
    c = selected(date(2026, 11, 30))
    assert kinds([c]) == ["new_selection"]
    c.notified.add("selected")
    assert kinds([c]) == []


def test_only_selected_campaigns_are_considered():
    for status in (Status.APPLIED, Status.REJECTED, Status.DONE):
        assert kinds([selected(date(2026, 10, 18), status=status)]) == []


def test_deadline_reminder_at_each_threshold():
    for days, key in ((3, "d-3"), (1, "d-1"), (0, "d-0")):
        c = selected(date(2026, 10, 17 + days), notified={"selected"})
        (n,) = plan_notifications([c], TODAY)
        assert n.kind == "deadline" and n.days_left == days and key in n.keys


def test_no_reminder_before_first_threshold():
    assert kinds([selected(date(2026, 10, 25), notified={"selected"})]) == []


def test_reminder_not_repeated_after_marking_keys():
    c = selected(date(2026, 10, 18), notified={"selected"})
    (n,) = plan_notifications([c], TODAY)
    c.notified.update(n.keys)
    assert kinds([c]) == []


def test_missed_threshold_sends_one_notification_covering_earlier_ones():
    c = selected(date(2026, 10, 19), notified={"selected"})  # D-2, d-3 이 아직 안 나간 상태
    (n,) = plan_notifications([c], TODAY)
    assert n.keys == ("d-3",)
    c.notified.update(n.keys)
    assert kinds([c]) == []


def test_overdue_notified_once():
    c = selected(date(2026, 10, 10), notified={"selected"})
    assert kinds([c]) == ["overdue"]
    c.notified.add("overdue")
    assert kinds([c]) == []


def test_missing_deadline_flagged_once():
    c = selected(None, notified={"selected"})
    assert kinds([c]) == ["deadline_missing"]
    c.notified.add("deadline_missing")
    assert kinds([c]) == []
