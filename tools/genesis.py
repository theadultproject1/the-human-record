"""Write the genesis event. Runs exactly once in the life of the archive.

The genesis event anchors the founding documents by hash: anyone
holding any copy of this log can verify which constitution, which
questionnaire, and which schemas this institution was born under.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahlib

# Only immutable founding texts are anchored: the Constitution, the
# versioned questionnaire, and the versioned schema. Living documents
# (MISSION, POLICY, ARCHITECTURE, LICENSING) evolve by governance and
# are deliberately NOT anchored — anchoring a document that is meant to
# change would make the genesis break every time we improve it.
ANCHORED = [
    "CONSTITUTION.md",
    "questions/v1.md",
    "questions/v1.json",
    "schema/CANONICAL.md",
    "schema/entry.v1.json",
    "schema/version.v1.json",
    "schema/event.v1.json",
]


def main():
    data = {
        "statement": (
            "The Human Record genesis. One number, at most three "
            "testimonies, kept forever. Registry number #000000001 is "
            "reserved forever; public numbering begins at #000000002. "
            "Founded under the immutable documents anchored below "
            "(Constitution, questionnaire, schema). The Mission, Policy, "
            "Architecture, and Licensing documents are living and are "
            "deliberately not anchored here."
        ),
        "documents": {
            rel: ahlib.file_sha256(ahlib.ROOT / rel) for rel in ANCHORED
        },
    }
    event = ahlib.append_event("GENESIS", data)
    print(f"genesis written: seq={event['seq']} hash={event['hash']}")


if __name__ == "__main__":
    main()
