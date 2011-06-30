from datetime import datetime, timedelta
import time
from mock import Mock, MagicMock, patch

from django.core import management
from django.test import TestCase
from django.contrib.auth.models import User

from stockandflow.models import Stock, StockRecord, StockFacetRecord, Flow
from stockandflow.tracker import ModelTracker
from stockandflow import periodic


class StockTest(TestCase):

    def register_flows(self, stock):
        for f in self.inflows:
            stock.register_inflow(f)
        for f in self.outflows:
            stock.register_outflow(f)

    def setUp(self):
        self.mock_qs = Mock()
        self.mock_qs.count.return_value = 999
        self.stock_args = ['test name', 'test_slug', self.mock_qs]
        self.inflows = [Mock(), Mock()]
        self.outflows = [Mock(), Mock()]



    def testCreateAStockShouldStoreProperties(self):
        args = self.stock_args
        s = Stock(*args)
        self.assertEqual(s.slug, args[0])
        self.assertEqual(s.name, args[1])
        self.assertEqual(s.queryset, args[2])

    def testStockAllShouldReturnTheQueryset(self):
        s = Stock(*self.stock_args)
        self.assertEqual(s.all(), self.mock_qs)

    def testRegisterInAndOutFlowsShouldKeepLists(self):
        s = Stock(*self.stock_args)
        self.register_flows(s)
        for i, m in enumerate(self.inflows):
            self.assertEqual(s.inflows[i], m, msg="Inflow not registered")
        for i, m in enumerate(self.outflows):
            self.assertEqual(s.outflows[i], m, msg="Outflow not registered")

    def testSaveCountShouldCheckTheCount(self):
        s = Stock(*self.stock_args)
        s.save_count()
        self.assertTrue(self.mock_qs.count.called)

    @patch.object(StockRecord, 'save')
    def testSaveCountShouldCreatesStockRecord(self, mock_save):
        s = Stock(*self.stock_args)
        s.save_count()
        self.assertTrue(mock_save.called)

    @patch.object(StockFacetRecord, 'save')
    def testSaveCountShouldCreatesStockFacetRecord(self, mock_save):
        from stockandflow.models import Facet
        f = Facet("test_slug", "test name", "test_field", [1,2])
        s = Stock(*self.stock_args)
        s.facets = [f]
        s.save_count()
        self.assertEqual(mock_save.call_count, 2)

    @patch.object(StockFacetRecord, 'save')
    def testSaveCountShouldPassThroughFieldPrefix(self, mock_save):
        from stockandflow.models import Facet
        f = Facet("test_slug", "test name", "test_field", [1,2])
        f.to_count = MagicMock()
        s = Stock(*self.stock_args)
        s.facets = [(f, "test_prefix")]
        s.save_count()
        self.assertEqual(f.to_count.call_args, (("test_prefix",), {}))

    def testMostRecentRecordShouldReturnCorrectStockRecord(self):
        s = Stock(*self.stock_args)
        s.save_count() # this would be the wrong record
        self.mock_qs.count.return_value = 111
        s.save_count()
        self.assertEqual(s.most_recent_record().count, 111)
        self.mock_qs.count.return_value = 222
        s.save_count()
        self.assertEqual(s.most_recent_record().count, 222)

    def testFlowIntoShouldReturnADictOfFlowsAndQuerysets(self):
        self.inflows = [Mock(), Mock()]
        self.outflows = [Mock(), Mock()]
        s = Stock(*self.stock_args)
        self.register_flows(s)
        rv = s.flows_into()
        self.assertEquals(len(rv), 2)
        self.assertTrue(self.inflows[0].all.called)
        self.assertEqual(rv[self.inflows[0]], self.inflows[0].all.return_value)
        self.assertTrue(self.inflows[1].all.called)
        self.assertEqual(rv[self.inflows[1]], self.inflows[1].all.return_value)

    def testFlowOutFromShouldReturnAListOfFlowsAndQuerysets(self):
        self.inflows = [Mock(), Mock()]
        self.outflows = [Mock(), Mock()]
        s = Stock(*self.stock_args)
        self.register_flows(s)
        rv = s.flows_outfrom()
        self.assertEquals(len(rv), 2)
        self.assertTrue(self.outflows[0].all.called)
        self.assertEqual(rv[self.outflows[0]], self.outflows[0].all.return_value)
        self.assertTrue(self.outflows[1].all.called)
        self.assertEqual(rv[self.outflows[1]], self.outflows[1].all.return_value)


class FlowTest(TestCase):

    def setUp(self):
        self.stock_mock = Mock()
        vals = [
           { "count" : 999, "args": ['test1 name', 'test1_slug', self.stock_mock] },
           { "count" : 444, "args": ['test2 name', 'test2_slug', self.stock_mock] },
        ]
        self.stocks = []
        for v in vals:
            v["args"][2].count.return_value = v["count"] #Set the mock's return value
            self.stocks.append(Stock(*v["args"]))
        self.args = {
                        "slug": "test_flow_slug", 
                        "name": "test flow name", 
                        "flow_event_model": Mock(),
                        "sources": (self.stocks[0],),
                        "sinks": (self.stocks[1],),
                    }

    def testCreateFlowShouldStoreProperties(self):
        f = Flow(**self.args)
        self.assertEqual(f.name, self.args["name"])
        self.assertEqual(f.slug, self.args["slug"])
        self.assertEqual(f.flow_event_model, self.args["flow_event_model"])
        self.assertEqual(f.sources, self.args["sources"])
        self.assertEqual(f.sinks, self.args["sinks"])

    def testCreateFlowShouldRegisterWithSourceAndSinkStocks(self):
        f = Flow(**self.args)
        self.assertEqual(self.stocks[0].outflows[0], f)
        self.assertEqual(self.stocks[1].inflows[0], f)

    def testFlowAddEventShouldReturnNoneIfSourceIsNotInSources(self):
        f = Flow(**self.args)
        self.assertTrue(f.add_event(Mock(), Mock(), self.stocks[1]) is None)

    def testCreateFlowBetweenMismatchedStocksShouldRaiseException(self):
        class MismatchClass():
            pass
        wrong_qs = StockRecord.objects.all() #could be any queryset
        s = Stock('test wrong class name', 'test_wc_slug', wrong_qs)
        self.args["sinks"] = (s,)
        self.assertRaises(ValueError, Flow, **self.args)

    def testCreateFlowEventShouldCreateDBRecord(self):
        # Create an object in the db - use stockrecord just because it is here and simple
        sr = StockRecord.objects.create(stock='no_stock', count=0)
        self.args["flow_event_model"] = Mock()
        f = Flow(**self.args)
        fe = f.add_event(sr, self.stocks[0], self.stocks[1])
        pos, kw = f.flow_event_model.call_args
        expect = {"flow": f.slug, "subject": sr, "source": self.stocks[0].slug,
                  "sink": self.stocks[1].slug }
        self.assertEqual(expect, kw)
        self.assertTrue(f.flow_event_model.return_value.save.called)

    def testFlowQuerysetShouldReturnAQSFilteredByTheFlowSlug(self):
        f = Flow(**self.args)
        objects_mock = f.flow_event_model.objects
        self.assertEqual(((), {"flow": f.slug}), objects_mock.filter.call_args)
        self.assertEqual(objects_mock.filter.return_value, f.queryset)

    def testFlowAllShouldReturnTheFlowQS(self):
        f = Flow(**self.args)
        self.assertEqual(f.queryset, f.all())

    def testFlowAllWithSourceAndOrSinkShouldReturnAQSFilteredByTheSink(self):
        f = Flow(**self.args)
        qs_mock = f.all()
        sink_mock = Mock()
        source_mock = Mock()
        rv_mock = f.all(sink=sink_mock)
        self.assertEqual(((), {"sink": sink_mock.slug}), qs_mock.filter.call_args)
        qs_mock.reset_mock()
        rv_mock = f.all(source=source_mock)
        self.assertEqual(((), {"source": source_mock.slug}), qs_mock.filter.call_args)
        qs_mock.reset_mock()
        rv_mock = f.all(sink=sink_mock, source=source_mock)
        self.assertEqual(((), {"source": source_mock.slug}), qs_mock.filter.call_args)
        qs2_mock = qs_mock.filter.return_value
        self.assertEqual(((), {"sink": sink_mock.slug}), qs2_mock.filter.call_args)


class ModelTrackerTest(TestCase):
    def setUp(self):
        self.staff_stock = Stock(slug="staff", name="Staff members",
                            queryset=User.objects.filter(is_staff=True))
        self.active_stock = Stock(slug="active", name="Active",
                             queryset=User.objects.filter(is_staff=False, 
                                                          is_active=True))
        self.inactive_stock = Stock(slug="inactive", name="Inactive",
                               queryset=User.objects.filter(is_staff=False, 
                                                            is_active=False))
        self.deactivating_flow = Flow(slug="deactivating", name="Deactivating",
                                      flow_event_model=Mock(),
                                      sources=[self.active_stock], 
                                      sinks=[self.inactive_stock])
        self.creating_flow = Flow(slug="creating", name="Creating",
                                  flow_event_model=Mock(),
                                  sources=[None], 
                                  sinks=[self.active_stock])
        self.args = {
            "fields_to_track": ("is_staff", "is_active"),
            "stocks": [self.staff_stock, self.active_stock, self.inactive_stock],
            "flows": [self.creating_flow, self.deactivating_flow],
            "states_to_stocks_func": self.user_states_to_stocks_f,
        }

    def user_states_to_stocks_f(self, prev_field_vals, cur_field_vals):
        return(self.user_state_to_stock(prev_field_vals), 
               self.user_state_to_stock(cur_field_vals)
              )
    def user_state_to_stock(self, field_vals):
        """
        Split users into a couple stocks for testing purposes
        """
        if field_vals == None: 
            return None, # This is an external stock
        is_staff, is_active = field_vals
        if is_staff: return self.staff_stock,
        if is_active: return self.active_stock,
        return self.inactive_stock,

    def testCheckForChangeShouldFlagChanges(self):
        mt = ModelTracker(**self.args)
        u = User(username="test1", is_active=True);
        u.save()
        cfe_mock = Mock()
        mt.create_flow_event = cfe_mock
        u2 = User.objects.get(username="test1")
        u2.is_active = False
        u2.save()
        self.assertTrue(cfe_mock.called)

    def testCreateFlowEventShouldCreateCorrectEvent(self):
        mt = ModelTracker(**self.args)
        u = User(username="test1", is_active=True);
        u.save()
        self.assertEqual(self.creating_flow.flow_event_model.call_count, 1)
        u2 = User.objects.get(username="test1")
        u2.is_active = False
        u2.save()
        self.assertEqual(self.deactivating_flow.flow_event_model.call_count, 1)
        u3 = User.objects.get(username="test1")
        u3.is_active = True
        u3.save()
        u4 = User.objects.get(username="test1")
        u4.is_active = False
        u4.save()
        self.assertEqual(self.deactivating_flow.flow_event_model.call_count, 2)

    def testModelTrackerShouldGenerateCreatingFlowEvent(self):
        mt = ModelTracker(**self.args)
        u = User(username="test1");
        u.save()
        self.assertTrue(self.creating_flow.flow_event_model.return_value.save.called)


class PeriodicScheduleShould(TestCase):
    def testHaveADefaultSchedule(self):
        self.assertTrue(periodic.schedule)

    def testCreateANewRecordForAnyNewTimePeriodsWithZeroCallCount(self):
        from stockandflow.periodic import PeriodicSchedule
        periodic.schedule.run()
        period = PeriodicSchedule.objects.get(frequency="weekly")
        self.assertEqual(period.call_count, 0)


class PeriodicScheduleRegistrationShould(TestCase):

    def setUp(self):
        periodic.schedule.reset_schedule()

    def tearDown(self):
        periodic.schedule.reset_schedule()

    def testAddMethodToSchedule(self):
        mock_callable = Mock()
        args = "test_arg",
        kwargs = {"a":"test_kwarg"}
        periodic.schedule.register(periodic.DAILY, mock_callable)
        self.assertEqual(periodic.schedule.entries[periodic.DAILY][0],
                         (mock_callable,(), {}))

    def testAddTwoMethodsToSchedule(self):
        mock_callable = Mock()
        mock_callable_2 = Mock()
        args = "test_arg",
        kwargs = {"a":"test_kwarg"}
        periodic.schedule.register(periodic.DAILY, mock_callable)
        periodic.schedule.register(periodic.DAILY, mock_callable_2,
                                   args, kwargs)
        self.assertEqual(periodic.schedule.entries[periodic.DAILY][1],
                         (mock_callable_2, args, kwargs))

    def testRaiseErrorWithANonFrequency(self):
        mock_callable = Mock()
        self.assertRaises(KeyError, periodic.schedule.register,
                          (periodic.schedule, "wrong", mock_callable), {})

class PeriodicScheduleRunnerShould(TestCase):
    def setUp(self):
        self.mock_callable = Mock()
        self.mock_callable_2 = Mock()
        self.args = "test_arg",
        self.kwargs = {"a":"test_kwarg"}

    def tearDown(self):
        periodic.schedule.reset_schedule()

    def testRunEntriesForAGivenFrequencyBasedOnCommandArgs(self):
        mock_callable = Mock()
        mock_callable_2 = Mock()
        args = "test_arg",
        kwargs = {"a":"test_kwarg"}
        periodic.schedule.register(periodic.DAILY, mock_callable)
        periodic.schedule.register(periodic.DAILY, mock_callable_2, args, kwargs)
        periodic.schedule.run_entries_for_frequency(periodic.DAILY)
        mock_callable.assertCalledOnceWithArgs((), {})
        mock_callable_2.assertCalledOnceWithArgs(args, kwargs)

    def testNotRunNewEntriesImmediately(self):
        mock_callable = Mock()
        periodic.schedule.register(periodic.DAILY, mock_callable)
        periodic.schedule.run()
        self.assertEqual(mock_callable.call_count, 0)

    def testCreateDbRecords(self):
        from stockandflow.periodic import PeriodicSchedule
        mock_callable = Mock()
        periodic.schedule.register(periodic.DAILY, mock_callable)
        periodic.schedule.run()
        entry = PeriodicSchedule.objects.get(frequency=periodic.DAILY)
        self.assertTrue(entry)

    def testNotSaveCallCountWhenTheRunOverlapsWithAnotherRun(self):
        #I'm not sure how to test this because it would need to change
        #the timestamp in another thread.
        pass

    @patch.object(periodic.schedule, "overlap_warning")
    def testCallOverlapWarningWhenRunWithAnOverlap(self, warning_mock):
        from stockandflow.periodic import PeriodicSchedule
        mock_callable = Mock()
        periodic.schedule.register(periodic.DAILY, mock_callable)
        periodic.schedule.run() # to register
        periodic.schedule.run() # to set timestamp
        entry = PeriodicSchedule.objects.get(frequency=periodic.DAILY)
        entry.call_count = None
        entry.save()
        periodic.schedule.run() # overlapping
        self.assertTrue(warning_mock.called)

    def testRunEntriesWhenThePeriodIsNew(self):
        mock_callable = Mock()
        mock_callable.func_name = "Mock function"
        periodic.schedule.run() # Get the frequencies into the db
        periodic.schedule.register(periodic.HOURLY, mock_callable)
        now = datetime.now()
        time_mock = Mock()
        with patch("stockandflow.periodic.datetime", new=time_mock):
            time_mock.now.return_value = now + timedelta(seconds=60*60+10) # an hour from now
            time_mock.side_effect = lambda *args, **kw: datetime(*args, **kw)
            periodic.schedule.run()
        self.assertTrue(mock_callable.called)

    def testRecordCallCountWhenThePeriodIsNew(self):
        mock_callable = Mock()
        mock_callable.func_name = "Mock function"
        mock_callable_2 = Mock()
        mock_callable_2.func_name = "Mock function 2"
        from stockandflow.periodic import PeriodicSchedule
        periodic.schedule.run() # Get the frequencies into the db
        periodic.schedule.register(periodic.HOURLY, mock_callable)
        periodic.schedule.register(periodic.HOURLY, mock_callable_2)
        now = datetime.now()
        time_mock = Mock()
        with patch("stockandflow.periodic.datetime", new=time_mock):
            time_mock.now.return_value = now + timedelta(seconds=60*60+10) # an hour from now
            time_mock.side_effect = lambda *args, **kw: datetime(*args, **kw)
            periodic.schedule.run()
        entry = PeriodicSchedule.objects.get(frequency=periodic.HOURLY)
        self.assertEqual(entry.call_count, 2)

    @patch.object(periodic.schedule, "run")
    def testRunAsAManagementCommand(self, run_mock):
        management.call_command("run_periodic_schedule")
        self.assertEqual(run_mock.call_count, 1)

    #write the callback functions and hook them up
    #create the stock amounts report



    #def testAdminAttribsShouldGetUpdatedForSpecificStocks(self):
        #mt = ModelTracker(**self.args)
        #expect = {
                    #"fake_1": "111",
                    #"fake_2": "222",
                 #}
        #active_admin = mt.stocks["active"].model_admin
        #self.assertEqual(active_admin.fake_1, "111")
        #self.assertEqual(active_admin.fake_2, "222")
        #staff_admin = mt.stocks["staff"].model_admin
        #self.assertEqual(staff_admin.fake_1, "999")

    #def testSaveCountShouldCallPreRecordCallable(self):
        #m = Mock()
        #s = Stock(*self.stock_args, pre_record_callable=m)
        #s.save_count()
        #self.assertTrue(m.called)

    #def testCreateWithNonIntegerFrequencyShouldRaiseError(self):
        #args = ['test name', 'test_slug', self.mock_qs, "month"]
        #self.assertRaises(InvalidFrequency, Stock, *args)

class PeriodicScheduleLogShould(TestCase):

    @patch('sys.stdout')
    def testPrintAMessageToStdOutDuringARun(self, stdout_mock):
        from stockandflow import periodic
        periodic.schedule.run()
        self.assertTrue(stdout_mock.write.called)
        periodic.schedule.run() # Get the frequencies into the db
        periodic.schedule.register(periodic.HOURLY, mock_callable)
        now = datetime.now()
        time_mock = Mock()
        with patch("stockandflow.periodic.datetime", new=time_mock):
            time_mock.now.return_value = now + timedelta(seconds=60*60+10) # an hour from now
            time_mock.side_effect = lambda *args, **kw: datetime(*args, **kw)
            periodic.schedule.run()
        self.assertTrue(self.mock_callable.called)

    def testRecordCallCountWhenThePeriodIsNew(self):
        from stockandflow.periodic import PeriodicSchedule
        periodic.schedule.run() # Get the frequencies into the db
        periodic.schedule.register(periodic.HOURLY, self.mock_callable)
        periodic.schedule.register(periodic.HOURLY, self.mock_callable_2)
        now = datetime.now()
        time_mock = Mock()
        with patch("stockandflow.periodic.datetime", new=time_mock):
            time_mock.now.return_value = now + timedelta(seconds=60*60+10) # an hour from now
            time_mock.side_effect = lambda *args, **kw: datetime(*args, **kw)
            periodic.schedule.run()
        entry = PeriodicSchedule.objects.get(frequency=periodic.HOURLY)
        self.assertEqual(entry.call_count, 2)

    @patch.object(periodic.schedule, "run")
    def testRunAsAManagementCommand(self, run_mock):
        management.call_command("run_periodic_schedule")
        self.assertEqual(run_mock.call_count, 1)

    #write the callback functions and hook them up
    #create the stock amounts report



    #def testAdminAttribsShouldGetUpdatedForSpecificStocks(self):
        #mt = ModelTracker(**self.args)
        #expect = {
                    #"fake_1": "111",
                    #"fake_2": "222",
                 #}
        #active_admin = mt.stocks["active"].model_admin
        #self.assertEqual(active_admin.fake_1, "111")
        #self.assertEqual(active_admin.fake_2, "222")
        #staff_admin = mt.stocks["staff"].model_admin
        #self.assertEqual(staff_admin.fake_1, "999")

    #def testSaveCountShouldCallPreRecordCallable(self):
        #m = Mock()
        #s = Stock(*self.stock_args, pre_record_callable=m)
        #s.save_count()
        #self.assertTrue(m.called)

    #def testCreateWithNonIntegerFrequencyShouldRaiseError(self):
        #args = ['test name', 'test_slug', self.mock_qs, "month"]
        #self.assertRaises(InvalidFrequency, Stock, *args)

class PeriodicScheduleLogShould(TestCase):

    @patch('sys.stdout')
    def testPrintAMessageToStdOutDuringARun(self, stdout_mock):
        from stockandflow import periodic
        periodic.schedule.run()
        self.assertTrue(stdout_mock.write.called)

class GeckoBoardStockLineChartViewShould(TestCase):
    def setUp(self):
        from django_geckoboard.tests.utils import TestSettingsManager
        self.settings_manager = TestSettingsManager()
        self.settings_manager.delete('GECKOBOARD_API_KEY')

    def tearDown(self):
        self.settings_manager.revert()

    def testReturnATupleOfValuesXAndYLabelsAndColor(self):
        """
        I need to write this test.
        """
        from nose.exc import SkipTest
        raise SkipTest

class FacetShould(TestCase):
    def testunitCallIteratorOnAValuesQuerySet(self):
        from stockandflow.models import Facet
        from django.db.models.query import ValuesQuerySet
        vqs = ValuesQuerySet()
        vqs.iterator = Mock()
        f = Facet("test_slug", "test_name", "test_field", vqs)
        f.values()
        vqs.iterator.assert_called()

    def testCreateAQObjectBasedOnAValue(self):
        from stockandflow.models import Facet
        f = Facet("test_slug", "test name", "test_field", [1,2])
        q = f.get_Q(1)
        self.assertEqual(str(q), "(AND: ('test_field', 1))")

    def testCreateAQObjectGivenAFieldPrefix(self):
        from stockandflow.models import Facet
        f = Facet("test_slug", "test name", "test_field", [1,2])
        q = f.get_Q(1, field_prefix="yada")
        self.assertEqual(str(q), "(AND: ('yada__test_field', 1))")

    def testCreateAGeneratorOfQObjectsForAllValues(self):
        from stockandflow.models import Facet
        f = Facet("test_slug", "test name", "test_field", [1,2])
        q_gen = f.to_count()
        rv = q_gen.next()
        self.assertEqual(rv[0], 1)
        self.assertEqual(str(rv[1]), "(AND: ('test_field', 1))")
        rv = q_gen.next()
        self.assertEqual(rv[0], 2)
        self.assertEqual(str(rv[1]), "(AND: ('test_field', 2))")

    def testCreateAGeneratorOfQObjectsForAllValuesWithAFieldPrefix(self):
        from stockandflow.models import Facet
        f = Facet("test_slug", "test name", "test_field", [1,2])
        q_gen = f.to_count("yada")
        rv = q_gen.next()
        self.assertEqual(rv[0], 1)
        self.assertEqual(str(rv[1]), "(AND: ('yada__test_field', 1))")
        rv = q_gen.next()
        self.assertEqual(rv[0], 2)
        self.assertEqual(str(rv[1]), "(AND: ('yada__test_field', 2))")

class ProcessShould(TestCase):
    def testGenerateAListOfFacetsSortedBySlugBasedOnTheStocks(self):
        from stockandflow.models import Stock, Facet
        from stockandflow.views import Process
        f1 = Facet("test_slug", "test name", "test_field", [1,2])
        f2 = Facet("test_slug", "test name", "test_field", [1,2])
        self.stock_args = []
        s1 = Stock('test name 1', 'test_slug_1', Mock())
        s2 = Stock('test name 2', 'test_slug_2', Mock())
        s1.facets = [f1]
        s2.facets = [f1, f2]
        process = Process("process_test", "process test", [s1, s2])
        self.assertEqual(process.facets, [f1, f2])



