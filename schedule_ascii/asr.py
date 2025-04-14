import os
import json
import argparse
import logging
from schedule_ascii.db import DBAdapter
from schedule_ascii.parser import JSONParser
from schedule_ascii.drawer import ScheduleDrawer, CapacityDrawer, FlawDrawer

logging.basicConfig()


def do_draw(output_file_path, config_file_path):
    json_parser = JSONParser(output_file_path)
    rel_path_name = os.path.basename(output_file_path)[:-5] + ".sqlite"
    db_filename = os.path.join(os.path.dirname(output_file_path), rel_path_name)
    db_adapter = DBAdapter(db_filename)
    db_adapter.init_tables()

    json_parser.store(db_adapter)

    # capacities
    capacity_drawer = CapacityDrawer(db_adapter)
    capacity_drawer.draw()

    # schedule
    schedule_drawer = ScheduleDrawer(db_adapter)
    schedule_drawer.init_shift_ascii_display()
    schedule_drawer.draw()

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

    parsed_args = parser.parse_args()

    do_draw(parsed_args.output_file_path, parsed_args.config_file_path)
