from os import path
import json
import logging
import datetime

from schedule_ascii.analytics import ScheduleAnalytics

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

        for i, bank_holiday in enumerate(self.json_data["schedule"]["bank_holidays"]):
            day_int = (datetime.date.fromisoformat(bank_holiday) - schedule_start).days
            if day_int >= 0:  # bank holidays may be out of schedule days
                db_adapter.insert(
                    "bank_holiday",
                    (
                        i,
                        day_int,
                    ),
                )

        for person_data in self.json_data["people"]:
            db_adapter.insert(
                "person",
                (
                    person_data["id"],
                    person_data["activity_rate"],
                    person_data["standard_weektime_hours"],
                    0,
                    0,
                    #                    person_data.get("work_target_minutes", 0) / 60,  # TODO: see if we still want to compute analytics own targets instead of using engine targets
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
                    shift_data["work_time"] / 60,
                    shift_data["effective_duration"] / 60,
                    shift_data["start_time"],
                    shift_data["end_time"],
                ),
            )
            for label in shift_data.get("labels", []):
                db_adapter.insert("shift_label", (shift_data["id"], label))

        # TODO: retro compatibility with scheduler legacy, to be removed
        names = [shift_data["id"] for shift_data in self.json_data["shifts"]]
        if "HOL" not in names:
            db_adapter.insert(
                "shift",
                (
                    "HOL",
                    "HOL",
                    "",
                    0,
                    "00:01:00",
                    "23:59:59",
                ),
            )
        if "OFF" not in names:
            db_adapter.insert(
                "shift",
                (
                    "OFF",
                    "OFF",
                    "",
                    0,
                    "00:01:00",
                    "23:59:59",
                ),
            )

        for i, task_data in enumerate(self.json_data["tasks"]):
            # TODO retro compatibility with scheduler legacy, to be removed
            if task_data["shift"] is None:
                task_data["shift"] = "HOL" if task_data["type"] == "VACATION" else "OFF"
            task_date = datetime.date.fromisoformat(task_data["day"])
            task_date_int = (task_date - schedule_start).days
            if not 0 <= task_date_int <= self.json_data["schedule"]["num_of_days"]:
                raise ValueError(
                    f"task day {task_data['day']} is outside schedule time span"
                )
            db_adapter.insert(
                "task",
                (
                    i,
                    task_data["person"],
                    task_data["shift"],
                    task_date_int,
                ),
            )
            if task_date.weekday() in [5, 6] and task_data["shift"] not in [
                "HOL",
                "OFF",
            ]:
                db_adapter.insert(
                    "task_label",
                    (i, "weekend"),
                )

        coverage_person_id = 0
        for i, coverage_data in enumerate(self.json_data["coverages"]):
            db_adapter.insert(
                "coverage",
                (
                    i,
                    coverage_data["min_value"],
                    coverage_data["max_value"],
                    coverage_data["shift"],
                    coverage_data["day"],
                ),
            )
            for person in coverage_data["people"]:
                db_adapter.insert(
                    "coverage_person",
                    (coverage_person_id, i, person),
                )
                coverage_person_id += 1

        for i, preallocation_data in enumerate(self.json_data["preallocations"]):
            db_adapter.insert(
                "preallocation",
                (
                    i,
                    (
                        preallocation_data["shift"]
                        if preallocation_data["type"] == 2
                        else "HOL" if preallocation_data["type"] == 1 else "OFF"
                    ),  # TODO: retro compatibility with scheduler legacy, to be removed
                    preallocation_data["person"],
                    preallocation_data["day"],
                ),
            )

        exclusion_id = 0
        for exclusion_data in self.json_data["day_exclusions"]:
            for person_id in exclusion_data["people"]:
                for shift_id in exclusion_data["shifts"]:
                    for day in exclusion_data["days"]:
                        db_adapter.insert(
                            "exclusion",
                            (exclusion_id, shift_id, person_id, day),
                        )
                        exclusion_id += 1

        for i, sequence in enumerate(self.json_data["sequences"]):
            db_adapter.insert(
                "sequence",
                (
                    i,
                    sequence["shift"],
                    sequence["group"],
                    sequence["order"],
                    sequence["day"],
                ),
            )

        db_adapter.commit()

        # store people aggregated data
        for person_id, night_count in db_adapter.select_person_nights():
            db_adapter.update(
                "person", f"id='{person_id}'", f"night_count={night_count}"
            )

        for person_id, weekend_count in db_adapter.select_person_weekends():
            db_adapter.update(
                "person", f"id='{person_id}'", f"weekend_count={weekend_count}"
            )

        for person_id, effective_hours in db_adapter.select_person_effective_hours():
            db_adapter.update(
                "person", f"id='{person_id}'", f"effective_hours={effective_hours/ 60}"
            )

        # establish int days used to compute hours targets
        schedule_analytics = ScheduleAnalytics(db_adapter)
        schedule_analytics.compute()
        target_int_days = schedule_analytics.target_int_days()

        for person_id, activity_rate, standard_weektime_hours in db_adapter.select(
            "person", ["id", "activity_rate", "standard_weektime_hours"]
        ):
            # compute holidays
            holidays_count = len(
                db_adapter.select(
                    "preallocation",
                    ["id"],
                    f"person_id='{person_id}' AND day in ({','.join([str(day) for day in target_int_days])}) AND shift_id='HOL'",
                )
            )
            db_adapter.update(
                "person",
                f"id='{person_id}'",
                f"holiday_hours={holidays_count * (activity_rate / 100) * standard_weektime_hours / 5}",
            )

            # remove holidays & bank holidays from int days target
            target_days_count = len(target_int_days) - holidays_count
            db_adapter.update(
                "person",
                f"id='{person_id}'",
                f"target_hours={target_days_count * (activity_rate / 100) * standard_weektime_hours / 5}",
            )

        db_adapter.commit()
