import re

from django.db import models
from django.contrib import admin

from model_utils.fields import AutoCreatedField


class Stock(object):
    """
    An accumulation defined by a queryset. 

    In the abstract a stock is a collection that is counted at a specific time
    interval, generating a StockRecord). The state of an object defines it's
    membership in a given stock. As a result, the words state and stock are
    roughly interchangeable.

    In the specific a stock is a subset of records for a given model that meet
    the conditions defined in the queryset.

    For example a User may have an "active" stock and an "inactive" stock
    defined by whether or not each user.is_active == True.

    Facets is a list of either facet objects or tuples of the form (facet,
    field_prefix). The field prefix maps the object of the stock to the object
    that is filtered in the facet. For example, if there is a User with a
    Profile and a facet on the Profile object like "yada"="true" then a User
    stock would use the field_prefix "profile" so that the field lookup in the facet becomes
    "profile__yada"=True.
    """

    def __init__(self, slug, name, queryset, facets=[]):
        self.name = name
        self.slug = slug
        self.queryset = queryset # defined but not executed at import time
        self.facets = facets
        self.inflows = []
        self.outflows = []


    def __str__(self):
        return "stock '%s'" % self.slug

    @property
    def subject_model(self):
        return self.queryset.model

    def register_inflow(self, flow):
        """
        Register an inward flow.
        """
        self.inflows.append(flow)

    def register_outflow(self, flow):
        """
        Register an outward flow.
        """
        self.outflows.append(flow)

    def most_recent_record(self):
        return StockRecord.objects.filter(stock=self.slug)[0]

    def all(self):
        """
        A shortcut for the queryset
        """
        return self.queryset

    def count(self):
        """
        A shortcut for a count of the queryset
        """
        return self.queryset.count()

    def flows_into(self):
        """
        A dict of flows that this stock as a sink in mapped to the queryset for
        those flow events.

        This method is used in views to get a lit of all the inflow events that
        impacted the stock.
        """
        rv = {}
        for f in self.inflows:
            rv[f] = f.all(sink=self)
        return rv

    def flows_outfrom(self):
        """
        A dict of flows that this stock as a source in mapped to the queryset for
        those flow events.

        This method is used in views to get a lit of all the outflow events that
        impacted the stock.
        """
        rv = {}
        for f in self.outflows:
            rv[f] = f.all(source=self)
        return rv

    def save_count(self):
        """
        Save a record of the current count for the stock and any facets.
        """
        sr = StockRecord.objects.create(stock=self.slug, count=self.queryset.count())
        for facet_item in self.facets:
            if not isinstance(facet_item, tuple):
                facet_item = (facet_item, "")
            facet, field_prefix = facet_item
            for value, q in facet.to_count(field_prefix):
                cnt = self.queryset.filter(q).count()
                srf = StockFacetRecord.objects.create(stock_record=sr, facet=facet.slug,
                                                      value=value, count=cnt)


class Facet(object):
    """
    A facet is used to split a stock or flow into sub-queries.
    
     - The name is used to refer to the facet.
     - The field lookup is the same as the left side of a kwarg in a filter function.
     - Values can either be a list or a ValuesQuerySet with flat=True. If it is a
       ValuesQuerySet then it will be re-evaluated at every use.
    """
    def __init__(self, slug, name, field_lookup, values):
        self.slug = slug
        self.name = name
        self.field_lookup = field_lookup
        self._given_values = values

    @property
    def values(self):
        if isinstance(self._given_values, models.query.ValuesQuerySet):
            return self._given_values.iterator()
        return self._given_values

    def get_Q(self, value, field_prefix=""):
        """
        Return a Q object that can be used in a filter to isolate this facet.

        The field_prefix string allows the field lookup to apply to related
        models by supplying the lookup path to the expected field.
        """
        if field_prefix:
            field_str = field_prefix + "__" + self.field_lookup
        else:
            field_str = self.field_lookup
        return models.Q(**{field_str: value})

    def to_count(self, field_prefix=""):
        """
        An generator of all the values and associated Q objects for this facet.
        Returns a list of tuples like (value, Q)

        The field_prefix string allows the field lookup to apply to related
        models by supplying the lookup path to the expected field.
        """
        return ((v, self.get_Q(v, field_prefix)) for v in self.values)


    
class Flow(object):
    """
    A named relationship between stocks representing the transition of an
    object from a source stock to a sink stock. A flow enables the transitions
    to measured over an interval of time to track the rate of occurence.

    A flow may have any number of source or sinks stocks. None is a valid
    source or sink that represents an external, or untracked stock. Any other
    class, such as an int or a string can be used a stock stand-in for creating
    flow events between states that do not have an associated Stock instance.

    Continuing the example in the Stock docstring, when a new user is created
    the flow from None to the stock "active". A flow to track this tranisition
    could be called "activating".  The activating flow would also have
    "inactive" as a source to handle the case where a previously inactive user
    becomes active again.

    The optional event_callables list is called whenever an flow event is created for
    this flow. It receives the flowed_obj, source and sink. An example use
    would be to send an email each time an activating flow occurs.
    """
    def __init__(self, slug, name, flow_event_model, sources=[], sinks=[],
                 event_callables=[]):
        self.slug = slug
        self.name = name
        self.flow_event_model = flow_event_model
        self.sources = sources
        self.sinks = sinks
        self.event_callables = event_callables
        self.queryset = flow_event_model.objects.filter(flow=self.slug)
        # If a flow connects stocks they must track the same class
        stock_cls = None
        stock_list = sources + sinks
        for s in stock_list: # Handles None stocks an no stocks
            if s:
                if isinstance(s, Stock):
                    s_cls = s.queryset.model
                else:
                    s_cls = s.__class__
                if not stock_cls:
                        stock_cls = s_cls
                elif s_cls != stock_cls:
                    raise ValueError("In %s the %s class %s does not match %s."
                                     % (self, s, s_cls, stock_cls))
        # Register the in and out flows
        for s in sources:
            if s and isinstance(s, Stock): s.register_outflow(self)
        for s in sinks:
            if s and isinstance(s, Stock): s.register_inflow(self)

    def __str__(self):
        return "flow '%s'" % self.slug

    @property
    def subject_model(self):
        return self.flow_event_model.subject.field.related.parent_model

    def add_event(self, flowed_obj, source=None, sink=None):
        """
        Record and return a flow event involving the (optional) object.
        If the flow does not connect the source and sink then return None.
        """
        if source is sink or source not in self.sources or sink not in self.sinks:
            return None
        args = { "flow": self.slug, "subject": flowed_obj }
        # If the source or sink is not a Stock instance then treat it as external
        args["source"] = source.slug if isinstance(source, Stock) else None
        args["sink"] = sink.slug if isinstance(sink, Stock) else None
        fe = self.flow_event_model(**args)
        fe.save()
        for c in self.event_callables:
            c(flowed_obj, source, sink)
        return fe

    def all(self, source=None, sink=None):
        """
        Return a queryset of all the events associated with this flow
        """
        qs = self.queryset
        if source:
            qs = qs.filter(source=source.slug)
        if sink:
            qs = qs.filter(sink=sink.slug)
        return qs

    def count(self, source=None, sink=None):
        """
        Return a count of all the events associated with this flow
        """
        return self.all(source, sink).count()


class StockRecord(models.Model):
    """
    A record of the count of a given stock at a point in time
    """
    stock = models.SlugField()
    timestamp = models.DateTimeField(auto_now_add=True)
    count = models.PositiveIntegerField()

    class Meta:
        ordering = ["-timestamp"]

class StockFacetRecord(models.Model):
    """
    A record of the count of a facet for a given stock at a point in time
    """
    stock_record = models.ForeignKey(StockRecord, db_index=True)
    facet = models.SlugField()
    value = models.CharField(max_length=200, db_index=True)
    count = models.PositiveIntegerField()

class StockRecordAdmin(admin.ModelAdmin):
    list_display=["timestamp", "stock", "count"]
    list_filter=["stock", "timestamp"]

admin.site.register(StockRecord, StockRecordAdmin)


class FlowEventModel(models.Model):
    """
    An abstract base class for the timestamped event of an object moving from 
    one stock to another

    Flow events combine to create a  flow variable that is measured over an
    interval of time. Therefore a flow would be measured per unit of time (say a
    year). Flow is roughly analogous to rate or speed in this sense.

    Subclasses must have a "subject" foreign key field.
    """
    flow = models.SlugField()
    timestamp = AutoCreatedField()
    source = models.SlugField(null=True, blank=True)
    sink = models.SlugField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return "%s (%s) at %s" % (self.flow, self.id, self.timestamp)


