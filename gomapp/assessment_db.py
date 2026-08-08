import uuid
from datetime import datetime
from db_users import db_connection
from config import damage_dict

def create_assessment(
    trial_uuid,
    user_uuid,
    grid_data,
    trial_rating=None,
    notes=None,
    assessment_date=None
):
    assessment_uuid = str(uuid.uuid4())

    if assessment_date is None:
        assessment_date = datetime.now().isoformat()

    with db_connection() as conn:

        # --------------------------------------------------
        # Assessment
        # --------------------------------------------------

        conn.execute("""
            INSERT INTO assessments (
                assessment_uuid,
                trial_uuid,
                user_uuid,
                assessment_date,
                trial_rating,
                notes,
                synced
            )
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (
            assessment_uuid,
            trial_uuid,
            user_uuid,
            assessment_date,
            trial_rating,
            notes
        ))

        # --------------------------------------------------
        # Persistent trees
        # --------------------------------------------------

        trees = conn.execute("""
            SELECT
                tree_uuid,
                row_num,
                col_num
            FROM trial_trees
            WHERE trial_uuid = ?
        """, (trial_uuid,)).fetchall()

        tree_lookup = {
            (row, col): tree_uuid
            for tree_uuid, row, col in trees
        }

        # --------------------------------------------------
        # Tree assessments
        # --------------------------------------------------

        for row in range(5):
            for col in range(5):

                data = grid_data[row][col]
                tree_uuid = tree_lookup[(row, col)]

                tree_assessment_uuid = str(uuid.uuid4())

                conn.execute("""
                    INSERT INTO tree_assessments (
                        tree_assessment_uuid,
                        assessment_uuid,
                        tree_uuid,
                        rating,
                        height,
                        diameter
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    tree_assessment_uuid,
                    assessment_uuid,
                    tree_uuid,
                    data["rating"],
                    data["height"],
                    data["diameter"]
                ))

                # ------------------------------------------
                # Damage agents
                # ------------------------------------------

                for damage in data["damage"]:
                    damage_code = damage_dict.get(damage["agent"])
                    conn.execute("""
                        INSERT INTO assessment_damage (
                            damage_uuid,
                            tree_assessment_uuid,
                            damage_code,
                            severity
                        )
                        VALUES (?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()),
                        tree_assessment_uuid,
                        damage_code,
                        damage["severity"]
                    ))

    return assessment_uuid

def load_assessment(assessment_uuid):
    DAMAGE_NAMES = {
        code: name
        for name, code in damage_dict.items()
    }

    with db_connection() as conn:

        # --------------------------------------------------
        # Assessment-level data
        # --------------------------------------------------

        assessment = conn.execute("""
            SELECT
                assessment_uuid,
                trial_uuid,
                user_uuid,
                assessment_date,
                trial_rating,
                notes
            FROM assessments
            WHERE assessment_uuid = ?
        """, (assessment_uuid,)).fetchone()

        if assessment is None:
            return None

        # --------------------------------------------------
        # Tree observations
        # --------------------------------------------------

        tree_rows = conn.execute("""
            SELECT
                tt.row_num,
                tt.col_num,
                ta.rating,
                ta.height,
                ta.diameter,
                ta.tree_assessment_uuid
            FROM tree_assessments ta
            JOIN trial_trees tt
              ON ta.tree_uuid = tt.tree_uuid
            WHERE ta.assessment_uuid = ?
            ORDER BY tt.tree_number
        """, (assessment_uuid,)).fetchall()

        # Start with empty/default grid
        grid = [
            [
                {
                    "rating": "Mis",
                    "damage": [],
                    "height": None,
                    "diameter": None
                }
                for col in range(5)
            ]
            for row in range(5)
        ]

        tree_assessment_lookup = {}

        for (
            row,
            col,
            rating,
            height,
            diameter,
            tree_assessment_uuid
        ) in tree_rows:

            grid[row][col] = {
                "rating": rating,
                "damage": [],
                "height": height,
                "diameter": diameter
            }

            tree_assessment_lookup[
                tree_assessment_uuid
            ] = (row, col)

        # --------------------------------------------------
        # Damage observations
        # --------------------------------------------------

        damage_rows = conn.execute("""
            SELECT
                d.tree_assessment_uuid,
                d.damage_code,
                d.severity
            FROM assessment_damage d
            JOIN tree_assessments ta
              ON d.tree_assessment_uuid =
                 ta.tree_assessment_uuid
            WHERE ta.assessment_uuid = ?
        """, (assessment_uuid,)).fetchall()

        for (
            tree_assessment_uuid,
            damage_code,
            severity
        ) in damage_rows:

            row, col = tree_assessment_lookup[
                tree_assessment_uuid
            ]

            grid[row][col]["damage"].append({
                "agent": DAMAGE_NAMES[damage_code],
                "severity": severity
            })

    return {
        "assessment_uuid": assessment[0],
        "trial_uuid": assessment[1],
        "user_uuid": assessment[2],
        "assessment_date": assessment[3],
        "trial_rating": assessment[4],
        "notes": assessment[5],
        "trees": grid
    }