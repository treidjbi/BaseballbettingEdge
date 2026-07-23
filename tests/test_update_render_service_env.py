from __future__ import annotations

import io
import json

import pytest

from scripts import update_render_service_env as helper


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class Transport:
    def __init__(self, pages, verified=None):
        self.pages = list(pages)
        self.verified = list(verified or pages)
        self.requests = []
        self.after_put = False

    def __call__(self, request, timeout=0):
        self.requests.append(request)
        if request.get_method() == "PUT":
            self.after_put = True
            return Response({})
        pages = self.verified if self.after_put else self.pages
        index = sum(r.get_method() == "GET" for r in self.requests) - 1
        if self.after_put:
            index = sum(r.get_method() == "GET" for r in self.requests[self.requests.index(next(r for r in self.requests if r.get_method() == "PUT")) + 1:]) - 1
        return Response(pages[index])


def _page(rows, cursor=None):
    return [{"envVar": row, "cursor": cursor} for row in rows]


def test_render_env_helper_dry_run_preserves_every_existing_key_and_value():
    transport = Transport([_page([{"key": "A", "value": "one"}, {"key": "B", "value": "two"}])])
    output = io.StringIO()
    result = helper.update_environment(
        service_id="svc", set_value="ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION=v2",
        unset_key=None, execute=False, api_key="secret", opener=transport, output=output,
    )
    assert result["environment"] == {"A": "one", "B": "two", "ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION": "v2"}
    assert not any(r.get_method() == "PUT" for r in transport.requests)


def test_render_env_helper_execute_puts_complete_list_and_verifies_target():
    verified = _page([{"key": "A", "value": "one"}, {"key": "ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", "value": "v2"}])
    transport = Transport([_page([{"key": "A", "value": "one"}])], [verified])
    helper.update_environment(service_id="svc", set_value="ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION=v2", unset_key=None, execute=True, api_key="secret", opener=transport, output=io.StringIO())
    put = next(r for r in transport.requests if r.get_method() == "PUT")
    assert json.loads(put.data) == [{"key": "A", "value": "one"}, {"key": "ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", "value": "v2"}]


def test_render_env_helper_paginates_every_page_before_full_list_put():
    first = _page([{"key": "A", "value": "one"}], "next")
    second = _page([{"key": "B", "value": "two"}])
    verified = _page([{"key": "A", "value": "one"}, {"key": "B", "value": "two"}, {"key": "ALTERNATIVE_PICK_SELECTION_MODE", "value": "off"}])
    transport = Transport([first, second], [verified])
    helper.update_environment(service_id="svc", set_value="ALTERNATIVE_PICK_SELECTION_MODE=off", unset_key=None, execute=True, api_key="secret", opener=transport, output=io.StringIO())
    put = next(r for r in transport.requests if r.get_method() == "PUT")
    assert {row["key"] for row in json.loads(put.data)} == {"A", "B", "ALTERNATIVE_PICK_SELECTION_MODE"}


def test_render_env_helper_can_restore_original_absence_with_unset():
    result = helper.update_environment(service_id="svc", set_value=None, unset_key="ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", execute=False, api_key="secret", opener=Transport([_page([{"key": "A", "value": "one"}])]), output=io.StringIO())
    assert result["original_state"] == "absent"
    assert result["environment"] == {"A": "one"}


def test_render_env_helper_never_prints_environment_values():
    output = io.StringIO()
    helper.update_environment(service_id="svc", set_value="ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION=v2", unset_key=None, execute=False, api_key="secret", opener=Transport([_page([{"key": "TOKEN", "value": "super-secret"}])]), output=output)
    assert "super-secret" not in output.getvalue()
    assert "v2" not in output.getvalue()


@pytest.mark.parametrize("set_value,unset_key", [
    ("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION=v2", "ALTERNATIVE_PICK_SELECTION_MODE"),
    ("UNAPPROVED=value", None),
])
def test_render_env_helper_rejects_more_than_one_change_or_unapproved_key(set_value, unset_key):
    with pytest.raises(ValueError):
        helper.update_environment(service_id="svc", set_value=set_value, unset_key=unset_key, execute=False, api_key="secret", opener=Transport([[]]), output=io.StringIO())
