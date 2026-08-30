f = open(rc:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend\app\models\schemas.py, r, encoding=utf-8)
c = f.read()
f.close()

old_schema = chr(34) + chr(34).join([s for s in [
    chr(34)+chr(34).join([
        chr(34).join([str(len( )), ])
    ])
])
)
# Simpler: do plain string replace via list of substrings
import re

old = open(rc:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend\app\models\schemas.py, r, encoding=utf-8).read()
src = "
                    duration_days: {type: INTEGER},
                },
                required: [phase, work_description],
            ],
        },

        cost_breakdown
"
dst = "
                    duration_days: {type: INTEGER},
                    depends_on: {type: ARRAY, items: {type: STRING}},
                    sequence: {type: INTEGER},
                },
                required: [phase, work_description],
            ],
        },

        cost_breakdown
"
print(SOW_SCHEMA marker found:, src in old)
if src in old and depends_on not in old:
    old = old.replace(src, dst, 1)
    print(Patched SOW_SCHEMA)
else:
    print(SOW_SCHEMA already patched or marker missing)

old2 = "    deliverables: list[str] = Field(default_factory=list)
    duration_days: int | None = 0"
new2 = "    deliverables: list[str] = Field(default_factory=list)
    duration_days: int | None = 0
    # Phase 4: WBS fields
    depends_on: list[str] = Field(default_factory=list)
    sequence: int = 0"
print(ScopeItem marker found:, old2 in old)
if old2 in old and depends_on not in old:
    old = old.replace(old2, new2, 1)
    print(Patched ScopeItem class)
else:
    print(ScopeItem already patched or marker missing)

open(rc:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend\app\models\schemas.py, w, encoding=utf-8).write(old)
print(Done)
