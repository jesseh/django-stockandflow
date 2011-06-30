from django.db import models


class ModelTracker(object):
    """
    Manage the stock counting and flow event generation for a given model.
    
    It generates flow events by monitoring for changes to the fields_to_track
    list, runs the old and new field values through the states_to_stocks_func
    function to figure out the source and sink stocks. Then it tries to checks
    if any of the flows will make an event for that transition.

    The states_to_stocks_func recieves a list of the field values in the order
    that they are dexclared in fields_to_track. The function must return a
    tuple of stock (it can be a 1-tuple). This allows a single model's state be
    composed of any number of sub-states/stocks. The resulting previous and
    current state tuples are then compared element by element.

    Thanks to carljm for the monitor in django-model-utils on which the
    change tracking is based.
    """
    def __init__(self, fields_to_track, states_to_stocks_func, stocks=[], flows=[]):
        try:
            self.model = stocks[0].subject_model
        except IndexError:
            try:
                self.model = flows[0].subject_model
            except IndexError:
                self.model = None
        self.fields_to_track = fields_to_track
        self.states_to_stocks_func = states_to_stocks_func
        self.stocks = stocks
        self.flows = flows
        # cache the flow lookup table
        self.flow_lookup = {}
        # property names to store initial state-defining field values
        self.tracker_attnames = map(lambda f: '_modeltracker_%s' % f, fields_to_track)
        # Establish signals to get change notifications
        models.signals.post_init.connect(self._save_initial, sender=self.model)
        models.signals.post_save.connect(self._check_for_change, sender=self.model)

    def __str__(self):
        return "ModelTracker for %s" % self.model

    def get_tracked_value(self, instance, idx):
        return getattr(instance, self.fields_to_track[idx])

    def _save_initial(self, sender, instance, **kwargs):
        """
        Receives the post_init signal.
        """
        for i, f in enumerate(self.fields_to_track):
            setattr(instance, self.tracker_attnames[i],
                    self.get_tracked_value(instance, i))

    def _check_for_change(self, sender, instance, created, **kwargs):
        """
        Receives the post_save signal.
        """
        previous = []
        current = []
        for i, f in enumerate(self.fields_to_track):
            previous.append(getattr(instance, self.tracker_attnames[i], None))
            current.append(self.get_tracked_value(instance, i))
        if created:
            previous = None
        if previous != current: # short circuit if nothing has changed
            sources, sinks = self.states_to_stocks_func(previous, current)
            for source, sink in zip(sources, sinks):
                if source is not sink: # short circuit if no change in state/stock
                    self.create_flow_event(source, sink, instance)

    def create_flow_event(self, source, sink, instance):
        """
        Find a flow to create the event based on the source and sink.

        First try a cache of previous matches. Then try to add the event
        with all the flows in this tracker. If an event is created update
        the cache for next time.
        """
        try: # Check the cache
            flow = self.flow_lookup[(source, sink)]
            if flow:
                flow.add_event(instance, source, sink)
        except KeyError:
            for flow in self.flows:
                if flow.add_event(instance, source, sink): break
            else:
                flow = None
            # Cache the result
            self.flow_lookup[(source, sink)] = flow

    def record_count(self):
        if self.pre_record_callable:
            self.pre_record_callable()
        for stock in self.stocks:
            stock.save_count()

