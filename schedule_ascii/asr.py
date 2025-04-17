import copy
import datetime
import os
import json
import argparse
import logging
from schedule_ascii.db import DBAdapter
from schedule_ascii.parser import JSONParser
from schedule_ascii.drawer import ScheduleDrawer, CapacityDrawer, FlawDrawer

logging.basicConfig()


def get_iso_months(start_date, end_date):
    """
    Return a list of elements like:
     [
       [start_date, last month day],
       [next month first day, next month last day],
       ...
       [next month first day, end_date
    ]
    for each month in the period betweens start_date and end_date
    """
    ret = []
    start_first_day = datetime.date(year=start_date.year, month=start_date.month, day=1)
    end_first_day = datetime.date(year=end_date.year, month=end_date.month, day=1)

    day = start_first_day
    while day <= end_first_day:
        date_plus_one_month = day + datetime.timedelta(days=31)

        ret.append([day, (date_plus_one_month - datetime.timedelta(days=1))])

        day = datetime.date(
            year=date_plus_one_month.year, month=date_plus_one_month.month, day=1
        )

    # adjust first month start day and last month end day
    ret[0][0] = start_date
    ret[-1][1] = end_date

    return ret


def get_days_int_by_month(start_date, end_date):
    """
    get int days by months, example for 2025-05-15 to 2025-06-20 => ((0, 16), (17, 37))
    0, 16 is the May int days range (first month)
    17, 37 is the June int days range (second / last month)
    """
    iso_days = get_iso_months(start_date, end_date)
    # adjust first month start and last month end
    ret = []
    for iso_start, iso_end in iso_days:
        ret.append([(iso_start - start_date).days, (iso_end - start_date).days + 1])

    return ret


def split_json(input_json_path):
    """
    Split JSON data by month and return a list of monthly JSON files
    """

    monthly_json_paths = []

    input_data = json.load(open(input_json_path))
    start_date = datetime.date.fromisoformat(input_data["schedule"]["start_day"])
    end_date = start_date + datetime.timedelta(
        days=input_data["schedule"]["num_of_days"]
    )

    if start_date > end_date:
        raise ValueError(
            "Schedule end month is prior to first month, is num_of_days negative ?"
        )

    month_days_int = get_days_int_by_month(start_date, end_date)

    for start_day_int, end_day_int in month_days_int:
        # update data by:
        #  removing everything that is out of this month
        #  applying an offset to int days
        copy_data = copy.deepcopy(input_data)
        copy_data["schedule"]["start_day"] = (
            start_date + datetime.timedelta(days=start_day_int)
        ).isoformat()
        copy_data["schedule"]["num_of_days"] = end_day_int - start_day_int

        # update coverages
        updated_coverages = []
        for coverage_data in copy_data["coverages"]:
            updated_day_index = coverage_data["day"] - start_day_int
            if (
                updated_day_index > 0
            ):  # negative index are out of this month and excluded
                coverage_data["day"] = updated_day_index
                updated_coverages.append(coverage_data)
        copy_data["coverages"] = updated_coverages

        # update day exclusions
        updated_exclusions = []
        for day_exclusion_data in copy_data["day_exclusions"]:
            if day_exclusion_data["days"]:
                updated_days_index = []
                for day_int in day_exclusion_data["days"]:
                    updated_day_index = day_int - start_day_int
                    if updated_day_index > 0:
                        updated_days_index.append(updated_day_index)
                if (
                    updated_days_index
                ):  # if empty, exclusion do not apply to this month and is removed
                    day_exclusion_data["days"] = updated_days_index
                    updated_exclusions.append(day_exclusion_data)
            else:  # exclusion apply to all days
                updated_exclusions.append(day_exclusion_data)
        copy_data["day_exclusions"] = updated_exclusions

        # update preallocations
        updated_preallocations = []
        for preallocation_data in copy_data["preallocations"]:
            updated_day_index = preallocation_data["day"] - start_day_int
            if updated_day_index > 0:
                preallocation_data["day"] = updated_day_index
                updated_preallocations.append(preallocation_data)
        copy_data["preallocations"] = updated_preallocations

        # update tasks
        updated_tasks = []
        for task_data in copy_data["tasks"]:
            task_day_int = (
                datetime.date.fromisoformat(task_data["day"]) - start_date
            ).days
            if start_day_int <= task_day_int <= end_day_int:
                updated_tasks.append(task_data)
        copy_data["tasks"] = updated_tasks

        month_json_path = f"{input_json_path.replace('.json','')}_{start_day_int}.json"
        json.dump(copy_data, open(month_json_path, "w"), indent=2)
        monthly_json_paths.append(month_json_path)

    return monthly_json_paths


def do_draw(output_file_path, config_file_path, by_month=False):

    output_files_path = []
    if by_month:
        # split JSON by month
        output_files_path.extend(split_json(output_file_path))
    else:
        output_files_path.append(output_file_path)

    for output_file_path in output_files_path:
        json_parser = JSONParser(output_file_path)
        rel_path_name = os.path.basename(output_file_path)[:-5] + ".sqlite"
        db_filename = os.path.join(os.path.dirname(output_file_path), rel_path_name)
        db_adapter = DBAdapter(db_filename)  # DBAdapter will delete db_filename
        db_adapter.init_tables()

        json_parser.store(db_adapter)

        # schedule
        schedule_drawer = ScheduleDrawer(db_adapter)
        schedule_drawer.init_shift_ascii_display()
        schedule_drawer.draw()

        # capacities
        capacity_drawer = CapacityDrawer(db_adapter)
        capacity_drawer.draw()

        # analytics
        flaw_drawer = FlawDrawer(db_adapter, json.load(open(config_file_path)))
        flaw_drawer.draw()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        prog="asr.py",
        description="Load JSON files to an sqlite database, display schedule & analytics,\n"
        "store db file in the execution directory\n",
    )
    parser.add_argument(
        "output_file_path", help="Engine output JSON file (usualy outputsch.json)"
    )
    parser.add_argument(
        "config_file_path", help="Engine config JSON file (usualy model_config.json)"
    )
    parser.add_argument(
        "--monthly",
        help="Draw output for each month in the schedule",
        action="store_true",
    )

    parsed_args = parser.parse_args()

    do_draw(
        parsed_args.output_file_path, parsed_args.config_file_path, parsed_args.monthly
    )
