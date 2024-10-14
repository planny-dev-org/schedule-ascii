from os import path
import json
import logging
import datetime


LOG = logging.getLogger(__name__)


class JSONParser:
    """
    parse json data and store to an sqlite DB file
    """

    def __init__(self, json_file_path):
        self.json_file_path = path.abspath(json_file_path)

        # load data file
        self.json_data = json.load(open(self.json_file_path))

    def store(self, db_adapter):
        """
        person(name, activity_rate, night_shifts, weekend_shifts, target_hours, holiday_hours, work_hours, debt_hours)
        shift(name, display_name, duration, start_time, end_time)
        task(person, day, shift)
        shift_label(shift_id, label)
        task_label(task_id, label)

        Store json data to db tables
        :return:
        """

        db_adapter.insert(
            "schedule",
            (
                0,
                self.json_data["schedule"]["start_day"],
                self.json_data["schedule"]["num_of_days"],
            ),
        )
        schedule_start = datetime.date.fromisoformat(
            self.json_data["schedule"]["start_day"]
        )

        for person_data in self.json_data["people"]:
            db_adapter.insert(
                "person",
                (
                    person_data["id"],
                    person_data["activity_rate"],
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                ),
            )

        for shift_data in self.json_data["shifts"]:
            db_adapter.insert(
                "shift",
                (
                    shift_data["id"],
                    shift_data["display_name"],
                    "",
                    shift_data["effective_duration"],
                    shift_data["start_time"],
                    shift_data["end_time"],
                ),
            )
            for label in shift_data.get("labels", []):
                db_adapter.insert("shift_label", (shift_data["id"], label))

        for i, task_data in enumerate(self.json_data["tasks"]):
            task_date = datetime.date.fromisoformat(task_data["day"])
            task_date_int = (task_date - schedule_start).days
            db_adapter.insert(
                "task",
                (
                    i,
                    task_data["person"],
                    task_data["shift"],
                    task_date_int,
                ),
            )
            if task_date.weekday() in [5, 6]:
                db_adapter.insert(
                    "task_label",
                    (i, "weekend"),
                )

        db_adapter.commit()

        # store people nights
        for person_id, night_count in db_adapter.select_person_nights():
            db_adapter.update(
                "person", f"id='{person_id}'", f"night_count={night_count}"
            )

        for person_id, weekend_count in db_adapter.select_person_weekends():
            db_adapter.update(
                "person", f"id='{person_id}'", f"weekend_count={weekend_count}"
            )

        db_adapter.commit()
