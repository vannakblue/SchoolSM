import logging
from datetime import datetime, date
from django.core.management.base import BaseCommand
from apps.attendance.models import AttendanceSetting
from apps.attendance.telegram_utils import send_daily_summary_telegram

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Checks daily attendance dispatch schedule and sends automated summary to Telegram.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forces dispatch regardless of schedule or time match.'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Target date in YYYY-MM-DD format (default: today).'
        )

    def handle(self, *args, **options):
        att_settings = AttendanceSetting.get_settings()
        force = options.get('force', False)
        date_str = options.get('date')

        target_date = date.today()
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid date format: {date_str}"))
                return

        if not att_settings.auto_daily_dispatch_enabled and not force:
            self.stdout.write(self.style.WARNING("Auto daily Telegram dispatch is disabled in Attendance Settings."))
            return

        now_dt = datetime.now()
        weekday_idx = str(target_date.isoweekday()) # '1' to '7'
        schedule_data = att_settings.daily_dispatch_schedule or {}
        scheduled_time_str = schedule_data.get(weekday_idx)

        if not scheduled_time_str and not force:
            self.stdout.write(self.style.NOTICE(f"No scheduled dispatch time configured for weekday {weekday_idx}."))
            return

        should_dispatch = force
        if not should_dispatch and scheduled_time_str:
            try:
                sched_h, sched_m = map(int, scheduled_time_str.split(':'))
                now_h, now_m = now_dt.hour, now_dt.minute
                now_total_mins = now_h * 60 + now_m
                sched_total_mins = sched_h * 60 + sched_m
                
                # Check if current time is within +/- 15 mins window of scheduled time
                if abs(now_total_mins - sched_total_mins) <= 15:
                    should_dispatch = True
                else:
                    self.stdout.write(self.style.NOTICE(f"Current time ({now_h:02d}:{now_m:02d}) is not within scheduled window ({scheduled_time_str})."))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error parsing scheduled time: {e}"))

        if should_dispatch:
            self.stdout.write(self.style.SUCCESS(f"Dispatching daily attendance summary for {target_date}..."))
            res = send_daily_summary_telegram(
                target_date=target_date,
                send_students=att_settings.auto_send_student_summary,
                send_teachers=att_settings.auto_send_teacher_summary
            )
            if res.get('success'):
                self.stdout.write(self.style.SUCCESS(f"Successfully dispatched: {res.get('message')}"))
            else:
                self.stderr.write(self.style.ERROR(f"Dispatch failed: {res.get('message')}"))
        else:
            self.stdout.write(self.style.NOTICE("Dispatch skipped (not scheduled or time condition not met)."))
