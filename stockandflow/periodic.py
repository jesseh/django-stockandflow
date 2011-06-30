import sys
import time
import calendar
from datetime import datetime

from django.db import models
from django.contrib import admin

# periods are in minutes

# Default period options
NEVER = "never"
MINUTELY = "minutely" #primarily for testing
TWELVE_MINUTELY = "twelve_minutely"
HOURLY = "hourly"
DAILY = "daily"
WEEKLY = "weekly"
TWO_WEEKLY = "two_weekly"
FOUR_WEEKLY = "four_weekly"

# The times are in minutes
FREQUENCIES = {}
FREQUENCIES["never"] = 0
FREQUENCIES["minutely"] = 1
FREQUENCIES["twelve_minutely"] = 12
FREQUENCIES["hourly"] = 60
FREQUENCIES["daily"] = FREQUENCIES["hourly"] * 24
FREQUENCIES["weekly"] = FREQUENCIES["daily"] * 7
FREQUENCIES["two_weekly"] = FREQUENCIES["weekly"] * 2
FREQUENCIES["four_weekly"] = FREQUENCIES["weekly"] * 4

class PeriodicSchedule(models.Model):
    """
    Periodically call a set of registered callable functions.

    This can be used, for example, to periodically count a stock. It could also
    be used to periodically decay objects from one stock to another.
    """

    frequency = models.SlugField()
    last_run_timestamp = models.DateTimeField(null=True)
    call_count = models.IntegerField(null=True, default=0)

    entries = {}

    def log(self, message):
        """
        A very basic logging function. Simply logs to stdout.
        """
        print >> sys.stdout, message

    def register(self, frequency, to_call, args=(), kwargs={}):
        """
        Register a callable with arguments to be called at the given frequency.
        The frequency must be one of the above constants.
        """
        if not FREQUENCIES[frequency]:
            raise ValueError("The frequency is invalid. it must be from the defined list.")
        if frequency == NEVER: return # Don't create an entry for something that never happens
        entry = (to_call, args, kwargs)
        try:
            self.entries[frequency].append(entry)
        except KeyError:
            self.entries[frequency] = [entry]

    def run_entries_for_frequency(self, frequency):
        """
        Run the entries for a given frequency.
        """
        self.log("Running %s entries." % frequency)
        call_count = 0
        for to_call, args, kwargs in self.entries.get(frequency, []):
            self.log("Running '%s'." % to_call.func_name)
            message = to_call(*args, **kwargs)
            self.log(message)
            call_count += 1
        return call_count


    def reset_schedule(self):
        """
        Used in testing to tearDown the entries.
        """
        self.entries = {}

    def run(self):
        """
        Run the schedule by checking if now is a higher period than the period
        of the last call for each frequency, and if so then run all the entries
        for that frequency.

        The period is determined by looking at the minutes since the epock, so
        it is safe to run this function repeatedly and it will still only run
        the entries for each frequency once per period.
        """
        now = datetime.now()
        now_seconds = int(time.mktime(now.utctimetuple()))
        self.log("Starting to run at %s." % now)
        period_mins_to_freq = dict((period, freq) for freq, period in FREQUENCIES.iteritems())
        for period_mins in sorted(period_mins_to_freq.keys()):
            if period_mins == 0: continue # Skip the never frequency
            freq = period_mins_to_freq[period_mins]
            to_run, created = PeriodicSchedule.objects.get_or_create(frequency=freq,
                    defaults={"last_run_timestamp": datetime.now(), "call_count": 0})
            if created:
                self.log("Not running %s frequency because it was just created." % freq)
                continue # Don't run just after creation because now may be mid-period
            last_run_timestamp = to_run.last_run_timestamp
            last_run_count = to_run.call_count
            if not last_run_timestamp:
                self.log("Giving defualt timestamp for %s" % freq)
                last_run_timestamp = datetime(1901,1,1)
                last_run_count = 0
            #Check for if this is overlapping a previous run
            elif to_run.call_count is None:
                self.log("Not running %s frequency because of an overlap." % freq)
                self.overlap_warning(freq, now)
            last_seconds = int(time.mktime(last_run_timestamp.utctimetuple()))
            now_period = now_seconds / 60 / period_mins
            last_period = last_seconds / 60 / period_mins
            if now_period > last_period:
                # Set that this is running in the database
                to_run.last_run_timestamp = now
                to_run.call_count = None #Mark to catch an overlap
                to_run.save()
                call_count = self.run_entries_for_frequency(freq)
                just_ran = PeriodicSchedule.objects.get(frequency=freq)
                if just_ran.last_run_timestamp == now:
                    just_ran.call_count = call_count
                    just_ran.save()
                else:
                    self.log("The run at %s has been overlapped." % freq)
                    # don't save the call count when there has been an overlap
            else:
                self.log("Not running %s because it is within the period" % freq)


    def overlap_warning(self, freq, timestamp):
        """
        Issue a warning about overlapping runs.
        This is a serperate function for easier testing.
        """
        print >> sys.stderr, "Overlapping run for '%s' frequency. There may have been an error, a slow process at %s" % (freq, timestamp)




# The schedule instance
schedule = PeriodicSchedule()

# Register to the normal admin
class PeriodicScheduleAdmin(admin.ModelAdmin):
    list_display = ["frequency", "last_run_timestamp", "call_count"]

admin.site.register(PeriodicSchedule, PeriodicScheduleAdmin)
