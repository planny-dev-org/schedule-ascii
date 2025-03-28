import os
import argparse
import logging
from schedule_ascii.db import DBAdapter
from schedule_ascii.parser import JSONParser
from schedule_ascii.drawer import ScheduleDrawer, CapacityDrawer

logging.basicConfig()


def do_draw(json_file_path):
    json_parser = JSONParser(json_file_path)
    rel_path_name = os.path.basename(json_file_path)[:-5] + ".sqlite"
    db_filename = os.path.join(os.path.dirname(json_file_path), rel_path_name)
    db_adapter = DBAdapter(db_filename)
    db_adapter.init_tables()

    json_parser.store(db_adapter)

    capacity_drawer = CapacityDrawer(db_adapter)
    capacity_drawer.draw()

    schedule_drawer = ScheduleDrawer(db_adapter)
    schedule_drawer.init_shift_ascii_display()
    for shift in db_adapter.select("shift", ["id", "ascii_display"]):
        print(f"{shift[0]} {shift[1]}")

    schedule_drawer.draw()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        prog="asr.py",
        description="Load JSON file to an sqlite database, display schedule & metrics,\n"
        "store db file at the root of JSON file path\n",
    )
    parser.add_argument("json_file_path", help="file to run (.mps)")

    parsed_args = parser.parse_args()

    do_draw(parsed_args.json_file_path)
