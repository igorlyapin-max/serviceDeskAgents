from __future__ import annotations

import subprocess
import textwrap
import unittest
from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "apps/admin-ui/static/app.js"


def js_function(source: str, name: str) -> str:
    marker = f"function {name}"
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f"Function not found: {name}")


class AdminUiDraftLabelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = APP_JS.read_text()
        functions = "\n".join(
            js_function(source, name)
            for name in (
                "stripDraftMetadata",
                "annotateDraftItem",
                "draftAwareCollectionItems",
                "draftLabelSuffix",
                "labelWithDraftState",
            )
        )
        cls.base_script = "\n".join(
            [
                "const assert = require('assert');",
                "const visibleLabels = { invalid: 'невалидно' };",
                "function cloneJson(value) { return JSON.parse(JSON.stringify(value ?? {})); }",
                functions,
            ]
        )

    def run_js(self, script: str) -> str:
        result = subprocess.run(
            ["node", "-e", f"{self.base_script}\n{script}"],
            check=True,
            text=True,
            capture_output=True,
        )
        return result.stdout

    def test_scoped_profile_draft_marks_only_target_new_profile(self) -> None:
        self.run_js(
            textwrap.dedent(
                """
                const active = [
                  { profile_id: 'profile.a', display_name: 'A', status: 'active' },
                  { profile_id: 'profile.b', display_name: 'B', status: 'active' },
                ];
                const draft = {
                  draft_id: 'cfgdraft-invalid',
                  status: 'invalid',
                  updated_at: '2026-07-03T05:13:55Z',
                  scope: {
                    type: 'collection_item',
                    collection: 'profiles',
                    id_key: 'profile_id',
                    id: 'profile.c',
                    action: 'upsert',
                  },
                };
                const draftItems = [
                  ...active,
                  { profile_id: 'profile.c', display_name: 'C', status: 'active' },
                ];

                const items = draftAwareCollectionItems(active, draftItems, 'profile_id', draft);

                assert.equal(items.length, 3);
                assert.equal(items[0].profile_id, 'profile.a');
                assert.equal(items[0].__draft_source, undefined);
                assert.equal(items[1].profile_id, 'profile.b');
                assert.equal(items[1].__draft_source, undefined);
                assert.equal(items[2].profile_id, 'profile.c');
                assert.equal(items[2].__draft_source, true);
                assert.equal(items[2].__draft_only, true);
                assert.equal(labelWithDraftState(items[2], items[2].display_name), 'C (только в черновике: невалидно)');
                """
            )
        )

    def test_scoped_profile_draft_marks_only_modified_target_profile(self) -> None:
        self.run_js(
            textwrap.dedent(
                """
                const active = [
                  { profile_id: 'profile.a', display_name: 'A', status: 'active' },
                  { profile_id: 'profile.b', display_name: 'B', status: 'active' },
                ];
                const draft = {
                  draft_id: 'cfgdraft-valid',
                  status: 'valid',
                  updated_at: '2026-07-03T05:13:55Z',
                  scope: {
                    type: 'collection_item',
                    collection: 'profiles',
                    id_key: 'profile_id',
                    id: 'profile.b',
                    action: 'upsert',
                  },
                };
                const draftItems = [
                  active[0],
                  { profile_id: 'profile.b', display_name: 'B changed', status: 'active' },
                ];

                const items = draftAwareCollectionItems(active, draftItems, 'profile_id', draft);

                assert.equal(items.length, 2);
                assert.equal(items[0].__draft_source, undefined);
                assert.equal(items[1].profile_id, 'profile.b');
                assert.equal(items[1].__draft_source, true);
                assert.equal(items[1].__draft_only, false);
                assert.equal(labelWithDraftState(items[1], items[1].display_name), 'B changed (черновик)');
                """
            )
        )

    def test_full_domain_draft_does_not_mark_unchanged_items(self) -> None:
        self.run_js(
            textwrap.dedent(
                """
                const active = [
                  { profile_id: 'profile.a', display_name: 'A', status: 'active' },
                  { profile_id: 'profile.b', display_name: 'B', status: 'active' },
                ];
                const draft = {
                  draft_id: 'cfgdraft-domain',
                  status: 'draft',
                  updated_at: '2026-07-03T05:13:55Z',
                };
                const draftItems = [
                  active[0],
                  { profile_id: 'profile.b', display_name: 'B changed', status: 'active' },
                  { profile_id: 'profile.c', display_name: 'C', status: 'active' },
                ];

                const items = draftAwareCollectionItems(active, draftItems, 'profile_id', draft);

                assert.equal(items.length, 3);
                assert.equal(items[0].__draft_source, undefined);
                assert.equal(items[1].__draft_source, true);
                assert.equal(items[1].__draft_only, false);
                assert.equal(items[2].__draft_source, true);
                assert.equal(items[2].__draft_only, true);
                """
            )
        )


if __name__ == "__main__":
    unittest.main()
