class DrawSchedule:
    """
    Output schedule ASCII printer
    """

    SHIFT_DISPLAY_SEQ = (
        "ABCDEFGHIJKLMNOPQRTSUVWXYZabcdefghijklmnopqrstuvwxyz1234567890@~#"
    )

    def __init__(self):
        self.block_width = 40
        self.day_width = 3
        self.task_map = {}  # key: person, value: {day int: [output tasks]}
        self.hour_counters = {}  # key: person, value: [effective time, target time]
        self.shift_display = {}  # shift display characters

    def init_task_map(self):
        """
        Read OutputTasks and create a dict map by person and days
        Update self.hour_counters dict as well

        Returned dict structure:
        {
          "person_id": {
              "0": ["A", "B"]
              }
        }
        """
        schedule = ScheduleManager.get()
        # init map using people and days
        for person in PersonManager.all():
            self.task_map[person.id] = {}
            self.hour_counters[person.id] = [0, 0]  # total effective time, hours delta
            for day in schedule.get_days():
                self.task_map[person.id][day] = []
        for output_task in OutputTaskManager.all():
            day = schedule.get_day(output_task.day)
            if output_task.shift:
                task_display = self.shift_display[output_task.shift.id]
                self.hour_counters[output_task.person.id][
                    0
                ] += output_task.shift.effective_duration
            else:
                # it's an off day or holiday
                task_display = "-"
            self.task_map[output_task.person.id][day].append(task_display)

        # compute counters
        weekdays_num = len(
            schedule.get_days(weekdays=[MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY])
        )
        for person in PersonManager.all():
            person_hour_target = (
                weekdays_num
                * person.activity_rate
                * person.standard_weektime_minutes
                / 5
            )
            self.hour_counters[person.id][1] = person_hour_target

    def draw_sep(self, size=100):
        """
        Draw a separator
        """
        print(f"{'-'*size}")

    def draw_list(self, labels):
        """
        Draw a list of labels at fixed positions
        """
        line = ""
        for label in labels:
            line += f"{label:<{self.block_width}}"
        print(f"{line}")

    def draw_indented_list(self, labels):
        """
        Same as draw_list but first position is fixed using self.block_width (larger block)
        Then, positions are fixed using self.day_width (smaller blocks)
        """
        line = f"{labels[0]:<{self.block_width}}"
        for label in labels[1:]:
            line += f"{label:<{self.day_width}}"
        print(f"{line}")

    def draw_schedule(self):
        """
        Draw schedule start day and num of days
        """
        schedule = ScheduleManager.get()
        self.draw_list(["start day", "num of days"])
        self.draw_list([schedule.start_day.isoformat(), schedule.num_of_days])

    def draw_shifts(self):
        """
        Draw shifts
        """
        self.draw_list(["shift id", "effective dur (h)", "work time (h)", "display"])
        display_iter = iter(self.SHIFT_DISPLAY_SEQ)
        for shift in ShiftManager.all():
            display = next(display_iter)
            self.shift_display[shift.id] = display
            self.draw_list(
                [
                    shift.id,
                    round(shift.effective_duration / HOUR_MINUTES, 1),
                    round(shift.work_time / HOUR_MINUTES, 1),
                    display,
                ]
            )
        self.draw_list(["OFF", "", "", "-"])
        self.draw_list(["HOLIDAY", "", "", "-"])

    def draw_people(self):
        """
        Draw people
        """
        self.draw_list(
            [
                "person id",
                "act rate",
                "std W worktime (h)",
                "max W worktime (h)",
                "nights count",
                "weekends count",
            ]
        )
        for person in PersonManager.all():
            # count people weekends and nights tasks
            night_number = 0
            weekend_number = 0
            tasks = OutputTaskManager.filter(people=[person])
            for task in tasks:
                if task.shift is not None:
                    if task.shift.end_time < task.shift.start_time:
                        night_number += 1
                    if task.day.weekday() in [5, 6]:
                        weekend_number += 1

            self.draw_list(
                [
                    person.id,
                    person.activity_rate * BASE_100_PERCENT,
                    round(person.standard_weektime_minutes / HOUR_MINUTES, 1),
                    round(person.max_weektime_minutes / HOUR_MINUTES, 1),
                    night_number,
                    weekend_number,
                ]
            )

    def draw_tasks(self):
        """
        Draw schedule tasks
        """
        schedule = ScheduleManager.get()

        # draw days
        days = list(range(schedule.num_of_days))
        is_we = []
        for day in days:
            iso_day = schedule.get_date_day(day)
            if iso_day.weekday() in [SATURDAY, SUNDAY]:
                is_we.append("X")
            else:
                is_we.append("")
        self.draw_indented_list([""] + days)
        self.draw_indented_list([""] + is_we)
        self.draw_sep(len(days) * self.day_width + self.block_width)
        # draw people tasks
        self.init_task_map()
        for person, days in self.task_map.items():
            hours_count = round(self.hour_counters[person][0] / HOUR_MINUTES)
            hours_target = round(self.hour_counters[person][1] / HOUR_MINUTES)
            delta = round(hours_count - hours_target)
            if delta > 0:
                delta = f"+{delta}"  # add + character
            labels = [f"{person} {hours_count}/{hours_target} ({delta}h)"]
            for day, tasks in days.items():
                labels.append("".join(tasks))
            self.draw_indented_list(labels)
        self.draw_sep(len(days) * self.day_width + self.block_width)

    def draw(self):
        try:
            self.draw_sep(104)
            self.draw_schedule()
            self.draw_sep(104)
            self.draw_shifts()
            self.draw_sep(104)
            self.draw_people()
            self.draw_sep(104)
            self.draw_tasks()
        except Exception as exc:
            print(f"can't draw schedule representation, exception {str(exc)}")
