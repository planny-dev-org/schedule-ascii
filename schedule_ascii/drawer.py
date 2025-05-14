import datetime
from schedule_ascii.analytics import (
    ScheduleAnalytics,
    HoursDeviation,
    ExtraHours,
    ShiftFairness,
    Sequences,
    WeekWorktime,
    WorkerPreference,
)


class BColors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class BaseDrawer:

    def __init__(self, db_adapter, model_config_data=None):
        self.block_width = 30
        self.day_width = 3
        self.db_adapter = db_adapter
        self.model_config_data = model_config_data

    def init_shift_ascii_display(self):
        """
        Set shift's table ascii_display column
        :return:
        """
        shift_display_seq = [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
            "P",
            "Q",
            "R",
            "T",
            "S",
            "U",
            "V",
            "W",
            "X",
            "Y",
            "Z",
            "a",
            "b",
            "c",
            "d",
            "e",
            "f",
            "g",
            "h",
            "i",
            "j",
            "k",
            "l",
            "m",
            "n",
            "o",
            "p",
            "q",
            "r",
            "s",
            "t",
            "u",
            "v",
            "w",
            "x",
            "y",
            "z",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "0",
        ]
        holiday_shift = self.db_adapter.select("shift", ["id"], "id='HOL'")
        if holiday_shift:
            self.db_adapter.update(
                "shift", f"id='{holiday_shift[0][0]}'", "ascii_display='|'"
            )
        off_shift = self.db_adapter.select("shift", ["id"], "id='OFF'")
        if off_shift:
            self.db_adapter.update(
                "shift", f"id='{off_shift[0][0]}'", "ascii_display='-'"
            )

        # find closer display using first shift id letter
        for shift in self.db_adapter.select("shift", ["id"], "ascii_display=''"):
            ascii_display = None
            char = shift[0][0]
            if char in shift_display_seq:
                ascii_display = shift_display_seq.pop(shift_display_seq.index(char))
            else:
                for method in "upper", "lower":
                    char = getattr(char, method)()
                    if char in shift_display_seq:
                        ascii_display = shift_display_seq.pop(
                            shift_display_seq.index(char)
                        )
                        break
            if ascii_display:
                self.db_adapter.update(
                    "shift", f"id='{shift[0]}'", f"ascii_display='{ascii_display}'"
                )

        # for all shifts without ascii display, assign one of the remaining display sequence items
        for shift in self.db_adapter.select("shift", ["id"], "ascii_display=''"):
            ascii_display = shift_display_seq.pop(0)
            self.db_adapter.update(
                "shift", f"id='{shift[0]}'", f"ascii_display='{ascii_display}'"
            )

    def draw_sep(self, size=100):
        """
        Draw a separator
        """
        print(f"{'-'*size}")

    def draw_list(self, labels, block_width=None):
        """
        Draw a list of labels at fixed positions
        """
        if block_width is None:
            block_width = self.block_width
        line = ""
        for label in labels:
            line += f"{label:<{block_width}}"
        print(f"{line}")

    def draw_indented_list(self, labels, first_width=None, width=None):
        """
        Same as draw_list but first position is fixed using self.block_width (larger block)
        Then, positions are fixed using self.day_width (smaller blocks)
        """
        if first_width is None:
            first_width = self.block_width
        if width is None:
            width = self.day_width
        line = f"{labels[0][:first_width]:<{first_width}}"
        for label in labels[1:]:
            line += f"{label:<{width}}"
        print(f"{line}")

    def draw_schedule(self):
        """
        Draw schedule table
        :return:
        """

        start_day, time_span_days = self.db_adapter.select(
            "schedule", ["start_day", "time_span_days"]
        )[0]
        self.draw_list(["start day", "num of days"])
        self.draw_list([start_day, time_span_days])
        self.draw_sep(155)

    def draw_shifts(self):
        """
        Draw shifts table
        :return:
        """
        self.draw_list(
            ["shift id", "duration", "start_time", "end_time", "display", "count"]
        )
        total_count = 0
        for shift_data in self.db_adapter.select(
            "shift",
            [
                "id",
                "display_name",
                "ascii_display",
                "duration",
                "start_time",
                "end_time",
            ],
        ):
            shift_id, display_name, ascii_display, duration, start_time, end_time = (
                shift_data
            )
            task_count = len(
                self.db_adapter.select("task", ["id"], f"shift_id='{shift_id}'")
            )
            self.draw_list(
                [
                    shift_id,
                    round(duration, 1),
                    start_time,
                    end_time,
                    ascii_display,
                    task_count,
                ]
            )
            total_count += task_count
        self.draw_list(["total", "", "", "", "", total_count])
        self.draw_sep(155)

    def draw_people(self):
        """
        Draw people table
        :return:
        """
        self.draw_indented_list(
            [
                "person id",
                "act rate",
                "Tg(h)",
                "Wo(h)",
                "Diff(h)",
                "Hol(h)",
                "Deb(h)",
                "Av(h)",
                "AvN(h)",
                "AvW(h)",
                "Nc",
                "Wc",
            ],
            first_width=30,
            width=15,
        )
        people_data = self.db_adapter.select(
            "person",
            [
                "id",
                "activity_rate",
                "standard_weektime_hours",
                "night_count",
                "weekend_count",
                "target_hours",
                "holiday_hours",
                "effective_hours",
                "debt_hours",
            ],
        )
        total_night = 0
        total_weekend = 0
        total_target = 0
        total_holiday = 0
        total_effective = 0
        total_debt = 0
        for person_data in people_data:
            (
                person_id,
                activity_rate,
                standard_weektime_hours,
                night_count,
                weekend_count,
                target_hours,
                holiday_hours,
                effective_hours,
                debt_hours,
            ) = person_data
            total_night += night_count
            total_weekend += weekend_count
            total_target += target_hours
            total_holiday += holiday_hours
            total_effective += effective_hours
            total_debt += debt_hours

            available_days = self.db_adapter.select_person_available_days(person_id)
            coverage_days = self.db_adapter.select_person_coverage_days(person_id)

            # available hours
            coeff = standard_weektime_hours * activity_rate / 500
            max_av_hours = int(len(coverage_days) * coeff)
            min_av_hours = int(
                #                (len(available_days) - len(unavailable_days)) * coeff,
                (len(available_days))
                * coeff
            )

            # available night hours
            night_shifts = [
                shift[0]
                for shift in self.db_adapter.select(
                    "shift", ["id"], "start_time>end_time"
                )
            ]

            nights_available_days = self.db_adapter.select_person_available_days(
                person_id, night_shifts
            )
            nights_coverage_days = self.db_adapter.select_person_coverage_days(
                person_id, night_shifts
            )
            max_night_hours = int(len(nights_coverage_days) * coeff)
            min_night_hours = int(len(nights_available_days) * coeff)

            # available weekend hours
            schedule_analytics = ScheduleAnalytics(self.db_adapter)
            schedule_analytics.compute()
            weekend_days = schedule_analytics.weekend_days
            we_coverage_days = [day for day in coverage_days if day not in weekend_days]
            we_available_days = [
                day for day in available_days if day not in weekend_days
            ]
            max_we_hours = int(len(we_coverage_days) * coeff)
            min_we_hours = int(len(we_available_days) * coeff)

            self.draw_indented_list(
                [
                    person_id,
                    activity_rate,
                    round(target_hours, 1),
                    round(effective_hours, 1),
                    round(effective_hours - target_hours, 1),
                    round(holiday_hours, 1),
                    round(debt_hours, 1),
                    f"{min_av_hours}-{max_av_hours}",
                    f"{min_night_hours}-{max_night_hours}",
                    f"{min_we_hours}-{max_we_hours}",
                    night_count,
                    weekend_count,
                ],
                first_width=30,
                width=15,
            )
        self.draw_indented_list(
            [
                "total",
                "",
                round(total_target, 1),
                round(total_effective, 1),
                round(total_effective - total_target, 1),
                round(total_holiday, 1),
                round(total_debt, 1),
                total_night,
                total_weekend,
            ],
            first_width=30,
            width=15,
        )
        self.draw_sep(137)


class ScheduleDrawer(BaseDrawer):
    """
    Schedule ASCII printer
    """

    def __init__(self, db_adapter):
        self.block_width = 30
        self.day_width = 3
        self.db_adapter = db_adapter
        super().__init__(db_adapter)

    def draw(self):
        self.draw_sep(104)

        # draw schedule
        self.draw_schedule()

        # draw shifts
        self.draw_shifts()

        # draw people
        self.draw_people()

        #############################
        # draw preallocations & tasks
        #############################
        people_data = self.db_adapter.select(
            "person",
            [
                "id",
            ],
        )
        start_day, time_span_days = self.db_adapter.select(
            "schedule", ["start_day", "time_span_days"]
        )[0]
        # days
        days = list(range(time_span_days))
        start_date = datetime.date.fromisoformat(start_day)
        is_we = []
        for day in days:
            iso_day = start_date + datetime.timedelta(days=day)
            if iso_day.weekday() in [5, 6]:
                is_we.append("X")
            else:
                is_we.append("")
        self.draw_indented_list([""] + days)
        self.draw_indented_list([""] + is_we)
        self.draw_sep(len(days) * self.day_width + self.block_width)

        # tasks & preallocations
        for person_data in people_data:
            tasks = self.db_adapter.select_person_tasks(person_data[0])  # 0: person id
            preals = self.db_adapter.select_person_preals(person_data[0])
            task_items = {}
            preal_items = {}
            for display, day, _, _, _ in tasks:
                task_items[day] = display
            for display, day, _ in preals:
                preal_items[day] = display
            task_labels = [person_data[0]]
            preal_labels = [f"{person_data[0]}[P]"]
            for day in days:
                task_labels.append(task_items.get(day, " "))
                preal_labels.append(preal_items.get(day, " "))
            self.draw_indented_list(task_labels)
            self.draw_indented_list(preal_labels)
            self.draw_sep(len(days) * self.day_width + self.block_width)
        self.draw_sep(120)


class CapacityDrawer(BaseDrawer):
    """
    Draw schedule capacity.
    For each shift for each day, draw 1 line with required minimal coverage and 1 line with count of available people
    """

    @classmethod
    def colorize(cls, needs_line, capacity_line):
        """
        Given 2 lists of values, convert to colorized strings based on values delta
        need value = capactity value => yellow
        need value > capactity value => red
        """
        if len(needs_line) != len(capacity_line):
            raise ValueError("needs and capacity lines must have same length")
        for i in range(len(needs_line)):
            need_value = needs_line[i]
            capacity_value = capacity_line[i]
            if isinstance(need_value, int) and isinstance(capacity_value, int):
                if need_value == capacity_value == 0:
                    continue
                elif need_value > capacity_value:
                    needs_line[i] = f"{BColors.FAIL}{need_value}{BColors.ENDC}"
                    capacity_line[i] = f"{BColors.FAIL}{capacity_value}{BColors.ENDC}"
                elif need_value == capacity_value:
                    needs_line[i] = f"{BColors.WARNING}{need_value}{BColors.ENDC}"
                    capacity_line[i] = (
                        f"{BColors.WARNING}{capacity_value}{BColors.ENDC}"
                    )

    def draw(self):
        start_day, time_span_days = self.db_adapter.select(
            "schedule", ["start_day", "time_span_days"]
        )[0]
        # days
        days = list(range(time_span_days))
        start_date = datetime.date.fromisoformat(start_day)

        # weekend line data
        is_we = []
        for day in days:
            iso_day = start_date + datetime.timedelta(days=day)
            if iso_day.weekday() in [5, 6]:
                is_we.append("X")
            else:
                is_we.append("")

        # header block
        self.draw_indented_list([""] + days)
        self.draw_indented_list([""] + is_we)
        self.draw_sep(len(days) * self.day_width + self.block_width)

        # needs & capacities
        total_capacity_people = []
        for i in range(len(days)):
            total_capacity_people.append([])
        total_covered = [0] * len(days)
        total_min_coverage = [0] * len(days)
        total_max_coverage = [0] * len(days)

        for shift_data in self.db_adapter.select(
            "shift",
            [
                "id",
                "display_name",
                "ascii_display",
                "duration",
                "start_time",
                "end_time",
            ],
        ):
            shift_id, display_name, ascii_display, duration, start_time, end_time = (
                shift_data
            )

            capacities_data = [f"{shift_id} capacity"]
            min_coverage_data = [f"{shift_id} min coverage"]
            covered_data = [f"{shift_id} covered"]
            max_coverage_data = [f"{shift_id} max coverage"]

            for i, day in enumerate(days):
                # estimate minimal coverage needed for this shift for this day
                min_coverage_count = 0
                max_coverage_count = 0
                for min_value, max_value in self.db_adapter.select(
                    "coverage",
                    ["min_value", "max_value"],
                    f"shift_id='{shift_id}' AND day={day}",
                ):
                    min_coverage_count += min_value
                    max_coverage_count += max_value
                min_coverage_data.append(min_coverage_count)
                max_coverage_data.append(max_coverage_count)
                total_min_coverage[i] += min_coverage_count
                total_max_coverage[i] += max_coverage_count

                # estimate count of available person to cover for this shift for this day
                statement = f"""
                SELECT person_id FROM coverage_person
                INNER JOIN coverage on coverage_person.coverage_id=coverage.id
                WHERE coverage.shift_id='{shift_id}'
                AND day={day}
                GROUP BY person_id
                """
                capacity = 0
                for person_data in self.db_adapter.cur.execute(statement).fetchall():
                    # check if person is available for this day
                    person_id = person_data[0]

                    # ignore person if preallocated on another shift or not working
                    is_preallocated = self.db_adapter.select(
                        "preallocation",
                        ["id"],
                        f"person_id='{person_id}' AND day={day} AND shift_id!='{shift_id}'",
                    )

                    # ignore person if excluded for this day and shift
                    is_excluded = self.db_adapter.select(
                        "exclusion",
                        ["id"],
                        f"person_id='{person_id}' AND day={day} AND shift_id='{shift_id}'",
                    )

                    if not is_preallocated and not is_excluded:
                        capacity += 1
                        if person_id not in total_capacity_people[day]:
                            total_capacity_people[day].append(person_id)

                capacities_data.append(capacity)

                # count coverage for this shift
                statement = f"""
                SELECT count('id') FROM task
                WHERE day={day} 
                AND shift_id='{shift_id}'
                """
                try:
                    coverage_count = self.db_adapter.cur.execute(statement).fetchall()[
                        0
                    ][0]
                except IndexError:
                    coverage_count = 0
                covered_data.append(coverage_count)
                total_covered[i] += coverage_count

            if (
                sum(min_coverage_data[1:])
                or sum(capacities_data[1:])
                or sum(covered_data[1:])
            ):
                # ignore line if no data
                #                self.colorize(min_coverage_data, capacities_data)  # TODO: find a solution that don't break indentation
                self.draw_indented_list(capacities_data)
                self.draw_indented_list(min_coverage_data)
                self.draw_indented_list(covered_data)
                self.draw_indented_list(max_coverage_data)
                self.draw_sep(len(days) * self.day_width + self.block_width)

        # draw totals
        #        self.colorize(total_needs_data, total_capacity_people)
        self.draw_indented_list(
            ["total capacity"]
            + [len(people_capacity) for people_capacity in total_capacity_people]
        )
        self.draw_indented_list(["total min coverage"] + total_min_coverage)
        self.draw_indented_list(["total covered"] + total_covered)
        self.draw_indented_list(["total max coverage"] + total_max_coverage)
        self.draw_sep(len(days) * self.day_width + self.block_width)

        # draw hours
        to_do_hours = 0
        contract_hours = 0
        to_do_night_hours = 0
        to_do_weekend_hours = 0
        schedule_analytics = ScheduleAnalytics(self.db_adapter)
        schedule_analytics.compute()
        weekend_days = schedule_analytics.weekend_days
        bank_holidays = [
            bank_holiday[0]
            for bank_holiday in self.db_adapter.select("bank_holiday", ["day"])
        ]
        week_days = set([day for day in range(time_span_days)]) - set(
            weekend_days + bank_holidays
        )

        for person_id, activity_rate, standard_weektime_hours in self.db_adapter.select(
            "person", ["id", "activity_rate", "standard_weektime_hours"]
        ):
            holiday_days = self.db_adapter.select_shift_tasks("HOL", person=person_id)
            contract_days = len(week_days) - len(holiday_days)
            contract_hours += (
                contract_days * activity_rate * standard_weektime_hours / 500
            )

        for day, min_value, shift_id in self.db_adapter.select(
            "coverage", ["day", "min_value", "shift_id"]
        ):
            start_time, end_time, duration = self.db_adapter.select(
                "shift", ["start_time", "end_time", "duration"], f"id='{shift_id}'"
            )[0]
            cov_duration = min_value * duration
            to_do_hours += cov_duration
            if start_time > end_time:
                to_do_night_hours += cov_duration
            if day in weekend_days:
                to_do_weekend_hours += cov_duration

        self.draw_indented_list(["total todo (h)"] + [round(to_do_hours, 0)])
        self.draw_indented_list([".. night todo (h)"] + [round(to_do_night_hours, 0)])
        self.draw_indented_list(
            [".. weekend todo (h)"] + [round(to_do_weekend_hours, 0)]
        )
        self.draw_indented_list(["contractual hours"] + [round(contract_hours, 0)])
        self.draw_sep()


class FlawDrawer(BaseDrawer):
    """
    Draw a table of flaws based on analytics classes:
        HoursDeviation,
        ExtraHours,
        ShiftFairness,
        Sequences,
        WeekWorktime,
        WorkerPreference,
    """

    def draw(self):

        analytics_instances = {}

        # hours
        if self.model_config_data is not None:
            for hour_objective in self.model_config_data.get("hour_deviation_obj", []):
                for i, people_group in enumerate(
                    hour_objective.get("people_groups", [])
                ):
                    hour_deviation = HoursDeviation(
                        self.db_adapter, people=people_group
                    )
                    hour_deviation.compute()
                    analytics_instances[f"Hour deviation, group {i}"] = hour_deviation
        else:
            self.draw_indented_list(["Hours objective (skipped)"])

        # extra hours
        extra_hours = ExtraHours(self.db_adapter)
        extra_hours.compute()
        analytics_instances["Extra hours"] = extra_hours

        # fairness
        if self.model_config_data is not None:
            for fairness_objective in self.model_config_data.get("shift_fairness_obj"):
                shift_id = fairness_objective["shift_id"]
                # TODO: use a person group when available in scheduler
                shift_fairness = ShiftFairness(
                    self.db_adapter,
                    shift=shift_id,
                    people=[
                        entry[0] for entry in self.db_adapter.select("person", ["id"])
                    ],
                )
                shift_fairness.compute()
                analytics_instances[f"Shift fairness ({shift_id})"] = shift_fairness
        else:
            self.draw_indented_list(["Fairness (skipped)"])

        # sequences
        sequence = Sequences(self.db_adapter)
        sequence.compute()
        analytics_instances[f"Sequences"] = sequence

        # week worktime
        week_worktime = WeekWorktime(self.db_adapter)
        week_worktime.compute()
        analytics_instances[f"Week worktime"] = week_worktime

        # preferences
        if self.model_config_data is not None:
            for i, preference_data in enumerate(
                self.model_config_data.get("preference_obj", [])
            ):
                preference = WorkerPreference(
                    self.db_adapter,
                    primary_people=preference_data["primary_people"],
                    secondary_people=preference_data["secondary_people"],
                    shift=preference_data["shift"],
                )
                preference.compute()
                analytics_instances[f"Preference ({preference_data['shift']})"] = (
                    preference
                )
        else:
            self.draw_indented_list(["Preference (skipped)"])

        self.draw_sep()
        self.draw_indented_list(
            ["objective efficiency", "score", "flaws min", "flaws", "flaws max"], 40, 25
        )
        for name, instance in analytics_instances.items():
            line = [
                name,
                f"{round(instance.score)} %",
                instance.flaws_min,
                instance.flaws,
                instance.flaws_max,
            ]
            self.draw_indented_list(line, 40, 25)
