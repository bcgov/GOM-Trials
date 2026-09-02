import uuid
from datetime import datetime
from db_users import db_connection
from config import damage_dict
from config import API_URL
from db_trials import ensure_trial_trees

def get_grid_direction(trial_uuid):
    with db_connection() as conn:
        row = conn.execute("""
            SELECT grid_direction
            FROM trials
            WHERE uuid = ?
        """, (trial_uuid,)).fetchone()

    if row is None:
        return None

    return row[0]

# def create_trial_assessment(
#     trial_uuid,
#     user_uuid,
#     data
# ):
#     assessment_uuid = str(uuid.uuid4())
#     assessment_date = datetime.now().isoformat()

def create_assessment(
    trial_uuid,
    user_uuid,
    grid_data = None,
    direction = None,
    trial_rating = None,
    notes = None,
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

        if direction is not None:
            conn.execute("""
                UPDATE trials
                SET grid_direction = ?
                WHERE uuid = ?
                AND grid_direction IS NULL
            """, (direction, trial_uuid))

        # --------------------------------------------------
        # Persistent trees
        # --------------------------------------------------
        if grid_data is not None:
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
        print("Loading assessment:", assessment_uuid)
        assessment = conn.execute("""
            SELECT
                a.assessment_uuid,
                a.trial_uuid,
                a.user_uuid,
                u.username,
                a.assessment_date,
                a.trial_rating,
                a.notes
            FROM assessments a
            LEFT JOIN users u
              ON a.user_uuid = u.user_uuid
            WHERE a.assessment_uuid = ?
        """, (assessment_uuid,)).fetchone()

        print("Loaded assessment:", assessment)

        if assessment is None:
            print("Assessment not found:", assessment_uuid)
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
                    "rating": "-",
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
                "agent": DAMAGE_NAMES.get(damage_code, ""),
                "severity": severity
            })

    return {
        "assessment_uuid": assessment[0],
        "trial_uuid": assessment[1],
        "user_uuid": assessment[2],
        "username": assessment[3],
        "assessment_date": assessment[4],
        "trial_rating": assessment[5],
        "notes": assessment[6],
        "trees": grid
    }

def get_trial_assessment_uuids(trial_uuid):

    with db_connection() as conn:

        rows = conn.execute("""
            SELECT assessment_uuid
            FROM assessments
            WHERE trial_uuid = ?
            ORDER BY assessment_date ASC,
                     created_at ASC
        """, (trial_uuid,)).fetchall()

    return [row[0] for row in rows]

import requests
import logging


def upload_assessments():
    """
    Upload all unsynced assessments to the server.

    Each assessment is sent as a complete unit:
        assessment
          -> tree assessments
              -> damage records

    Assessments are marked synced only after the server
    confirms that the complete request succeeded.
    """

    # ------------------------------------------------------
    # Build payload from SQLite
    # ------------------------------------------------------

    with db_connection() as conn:

        assessments = conn.execute("""
            SELECT
                a.assessment_uuid,
                a.trial_uuid,
                a.user_uuid,
                a.assessment_date,
                a.trial_rating,
                a.notes,
                t.grid_direction
            FROM assessments a
            JOIN trials t
            ON a.trial_uuid = t.uuid
            WHERE a.synced = 0
            ORDER BY a.assessment_date
        """).fetchall()

        if not assessments:
            logging.info("No assessments to sync.")
            return True

        payload_assessments = []

        for (
            assessment_uuid,
            trial_uuid,
            user_uuid,
            assessment_date,
            trial_rating,
            notes,
            grid_direction
        ) in assessments:

            # --------------------------------------------------
            # Tree assessments + persistent tree information
            # --------------------------------------------------

            tree_rows = conn.execute("""
                SELECT
                    ta.tree_assessment_uuid,
                    ta.tree_uuid,
                    tt.tree_number,
                    tt.row_num,
                    tt.col_num,
                    ta.rating,
                    ta.height,
                    ta.diameter
                FROM tree_assessments ta
                JOIN trial_trees tt
                  ON ta.tree_uuid = tt.tree_uuid
                WHERE ta.assessment_uuid = ?
                ORDER BY tt.tree_number
            """, (assessment_uuid,)).fetchall()

            trees = []

            for (
                tree_assessment_uuid,
                tree_uuid,
                tree_number,
                row_num,
                col_num,
                rating,
                height,
                diameter
            ) in tree_rows:

                # ----------------------------------------------
                # Damage records for this tree assessment
                # ----------------------------------------------

                damage_rows = conn.execute("""
                    SELECT
                        damage_uuid,
                        damage_code,
                        severity
                    FROM assessment_damage
                    WHERE tree_assessment_uuid = ?
                """, (tree_assessment_uuid,)).fetchall()

                damage = [
                    {
                        "damage_uuid": damage_uuid,
                        "damage_code": damage_code,
                        "severity": severity
                    }
                    for (
                        damage_uuid,
                        damage_code,
                        severity
                    ) in damage_rows
                ]

                trees.append({
                    "tree_assessment_uuid":
                        tree_assessment_uuid,

                    "tree_uuid":
                        tree_uuid,

                    "tree_number":
                        tree_number,

                    "row_num":
                        row_num,

                    "col_num":
                        col_num,

                    "rating":
                        rating,

                    "height":
                        height,

                    "diameter":
                        diameter,

                    "damage":
                        damage
                })

            payload_assessments.append({
                "assessment_uuid":
                    assessment_uuid,

                "trial_uuid":
                    trial_uuid,

                "user_uuid":
                    user_uuid,

                "assessment_date":
                    assessment_date,

                "trial_rating":
                    trial_rating,

                "notes":
                    notes,

                "trees":
                    trees,

                "grid_direction":
                    grid_direction
            })

    # ------------------------------------------------------
    # Send to Plumber
    # ------------------------------------------------------

    payload = {
        "assessments": payload_assessments
    }

    logging.info(
        "Uploading %d assessment(s)...",
        len(payload_assessments)
    )

    try:

        response = requests.post(
            f"{API_URL}/assessments",
            json=payload,
            timeout=30
        )

    except requests.RequestException as e:

        logging.error(
            "Assessment sync request failed: %s",
            e
        )

        return False

    # ------------------------------------------------------
    # Check response
    # ------------------------------------------------------

    if response.status_code != 200:

        logging.error(
            "Assessment sync failed. STATUS %s BODY %s",
            response.status_code,
            response.text
        )

        return False

    try:
        result = response.json()

    except ValueError:

        logging.error(
            "Assessment sync returned invalid JSON: %s",
            response.text
        )

        return False

    if not result.get("success", False):

        logging.error(
            "Assessment sync rejected by server: %s",
            result
        )

        return False

    # ------------------------------------------------------
    # Mark uploaded assessments as synced
    # ------------------------------------------------------

    uploaded_uuids = [
        assessment["assessment_uuid"]
        for assessment in payload_assessments
    ]

    with db_connection() as conn:

        conn.executemany("""
            UPDATE assessments
            SET synced = 1
            WHERE assessment_uuid = ?
        """, [
            (assessment_uuid,)
            for assessment_uuid in uploaded_uuids
        ])

    logging.info(
        "Successfully synced %d assessment(s).",
        len(uploaded_uuids)
    )

    return True

def download_assessments(since=None):

    params = {}

    if since is not None:
        params["since"] = since

    try:
        response = requests.get(
            f"{API_URL}/assessments",
            params=params,
            timeout=30
        )

    except requests.RequestException as e:
        logging.error(
            "Assessment download failed: %s",
            e
        )
        return False

    if response.status_code != 200:
        logging.error(
            "Assessment download failed. "
            "STATUS %s BODY %s",
            response.status_code,
            response.text
        )
        return False

    try:
        result = response.json()
    except ValueError:
        logging.error(
            "Assessment download returned invalid JSON: %s",
            response.text
        )
        return False

    assessments = result.get(
        "assessments",
        []
    )

    logging.info(
        "Downloaded %d assessment(s).",
        len(assessments)
    )

    for assessment in assessments:
        save_downloaded_assessment(
            assessment
        )

    return True

def save_downloaded_assessment(assessment):
    with db_connection() as conn:

        assessment_uuid = (
            assessment["assessment_uuid"]
        )

        trial_uuid = (
            assessment["trial_uuid"]
        )
        ensure_trial_trees(trial_uuid)
        # --------------------------------------------------
        # Grid direction
        # --------------------------------------------------

        grid_direction = assessment.get(
            "grid_direction"
        )

        print(
            "grid_direction:",
            repr(grid_direction),
            type(grid_direction)
        )

        if grid_direction is not None:

            conn.execute("""
                UPDATE trials
                SET grid_direction = ?
                WHERE uuid = ?
                  AND grid_direction IS NULL
            """, (
                grid_direction,
                trial_uuid
            ))

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
                created_at,
                synced
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)

            ON CONFLICT(assessment_uuid)
            DO NOTHING
        """, (
            assessment_uuid,
            trial_uuid,
            assessment.get("user_uuid"),
            assessment["assessment_date"],
            assessment.get("trial_rating"),
            assessment.get("notes"),
            assessment.get("created_at"),
        ))

        # --------------------------------------------------
        # Trees
        # --------------------------------------------------

        for tree in assessment.get(
            "trees",
            []
        ):

            # Permanent trial tree
            conn.execute("""
                INSERT INTO trial_trees (
                    tree_uuid,
                    trial_uuid,
                    tree_number,
                    row_num,
                    col_num
                )
                VALUES (?, ?, ?, ?, ?)

                ON CONFLICT(tree_uuid)
                DO NOTHING
            """, (
                tree["tree_uuid"],
                trial_uuid,
                tree["tree_number"],
                tree["row_num"],
                tree["col_num"]
            ))

            # Tree assessment
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

                ON CONFLICT(tree_assessment_uuid)
                DO NOTHING
            """, (
                tree["tree_assessment_uuid"],
                assessment_uuid,
                tree["tree_uuid"],
                tree.get("rating") or "Mis",
                tree.get("height"),
                tree.get("diameter")
            ))

            # Damage
            for damage in tree.get(
                "damage",
                []
            ):

                conn.execute("""
                    INSERT INTO assessment_damage (
                        damage_uuid,
                        tree_assessment_uuid,
                        damage_code,
                        severity
                    )
                    VALUES (?, ?, ?, ?)

                    ON CONFLICT(damage_uuid)
                    DO NOTHING
                """, (
                    damage["damage_uuid"],
                    tree["tree_assessment_uuid"],
                    damage["damage_code"],
                    damage.get("severity")
                ))