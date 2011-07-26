from operator import attrgetter

from django.shortcuts import redirect
from django.views.generic.list_detail import object_detail
from django.core.urlresolvers import reverse
from django.template import loader
from django import forms
from django.http import QueryDict

from stockandflow.models import StockRecord, StockFacetQuerySet

class FacetForm(forms.Form):
    def __init__(self, facet_selection, *args, **kwargs):
        super(FacetForm, self).__init(*args, **kwargs)
        facets = facet_selection.process.facets
        for facet in facets:
            if facet.slug == facet_selection.slug:
                initial = facet_selection.value
            else:
                initial = None
            self.fields[facet.slug] = forms.ChoiceField(label=facet.name,
                    choices=facet.choices, initial=initial)


class FacetSelection(object):
    """
    This class is used to select the facets that should be applied.  The
    selected facets depend on information that is placed in the query string of
    a GET request.
    """
    def __init__(self, request=None, facet_slug=None, facet_value=None):
        """
        Values are either given or extracted from the request.
        """
        if request:
            self.slug = request.GET.get("facet_slug", "")
            self.value = request.GET.get("facet_value", "")
        if facet_slug is not None:
            self.slug = facet_slug
        if facet_value is not None:
            self.value = facet_value


    def stock_facet_qs(self, stock):
        return StockFacetQuerySet(stock=stock, facet_slug=self.slug, facet_value=self.value)

    def update_query_dict(self, query_dict):
        """
        Set the values relevant to this object in the query dict.
        """
        query_dict["facet_slug"] = self.slug
        query_dict["facet_value"] = self.value
        return query_dict

    def form(self, request, valid_redirect=None):
        """
        If valid_redirect is not defined it will just reload the current URL with an updated
        GET query string.

        NOTE: THE IS AN UNTESTED WORK IN PROGRESS
        """
        if request.method == 'POST':
            form = FacetForm(self, request.POST)
            if form.is_valid():
                # Process the data in form.cleaned_data
                # Find the facet that has a value, set the slug and value, update the querydict and redirect.
                for slug, value in enumerate(form.cleaned_data):
                    if value:
                        self.slug = slug
                        self.value = value
                        break
                if valid_redirect:
                    url = valid_redirect
                else:
                    url = request.path_info
                    #Update the GET params
                try:
                    query_str = self.update_query_dict(request.GET.copy()).urlencode()
                except ValueError:
                    query_str = None
                if query_str: 
                    url += "?%s" % query_str
                return redirect(url)
        else:
            form = FacetForm(self)
        return form


class StockSelection(object):
    """
    This class is used to select the stock that should be applied.  The
    selected stock depends on information that is placed in the query string of
    a GET request.
    """
    def __init__(self, process, request=None, stock=None):
        """
        Values are either given or extracted from the request.
        """
        if stock is None:
            stock_slug = request.GET.get("stock_slug", "")
            self.stock = process.stock_lookup[stock_slug] # raises a key error if invalid stoc
        else:
            self.stock = stock

    def update_query_dict(self, query_dict):
        """
        Set the values relevant to this object in the query dict.
        """
        query_dict["stock_slug"] = self.stock.slug
        return query_dict


class StockSequencer(object):
    """
    This class is used to create a view that iterates through a faceted stock
    based.  The iterating depends on information that is placed in the query
    string of a GET request.
    """
    def __init__(self, stock_selection=None, facet_selection=None, index=None, request=None):
        """
        Values are extracted from the request.

        This will raise an IndexError if there is no object at the given index.
        """
        if index is None:
            if request:
                self.index = int(request.GET.get("index", 0))
            else:
                self.index = 0
        else:
            self.index = index
        self.stock_selection = stock_selection
        self.facet_selection = facet_selection
        self.stock_facet_qs = facet_selection.stock_facet_qs(self.stock_selection.stock)
        try:
            self.object_at_index = self.stock_facet_qs[self.index]
        except IndexError:
            self.object_at_index = None

    @property
    def stock(self):
        return self.stock_selection.stock

    def next(self, current_object_id=None, current_slug=None, slug_field=None):
        return self._step(1, current_object_id, current_slug, slug_field)

    def previous(self, current_object_id=None, current_slug=None, slug_field=None):
        return self._step(-1, current_object_id, current_slug, slug_field)

    def _step(self, step_amount, current_object_id=None, current_slug=None, slug_field=None):
        """
        Return the next or previous in the sequence based on the step_amount.
        If cur_object_id and slug are None then the previous object is index +
        step.

        If current_object or slug is not None and if the object at index is not
        equal to current object's id or slug then previous will have the same
        index, so simply return self.

        Raises StopIteration if the next index is invalid.
        """
        if current_object_id is not None and current_object_id != self.object_at_index:
            return self
        elif current_slug is not None:
            if slug_field is None:
                raise ValueError("There must be a slug_field give if current_slug is given.")
            if current_slug != self.get_object()[slug_field]:
                return self
        else:
            if self.index + step_amount < 0:
                raise StopIteration
            try:
                return StockSequencer(self.stock_selection, self.facet_selection,
                                      self.index + step_amount)
            except IndexError:
                raise StopIteration

    def update_query_dict(self, query_dict):
        """
        Set the values relevant to this object in the query dict.
        """
        query_dict = self.stock_selection.update_query_dict(query_dict)
        if self.facet_selection:
            query_dict = self.facet_selection.update_query_dict(query_dict)
        query_dict["index"] = self.index
        return query_dict

    def query_str(self):
        """
        Update the request's GET query string with the values in this object
        and return the resulting query url encoded string.
        """
        qd = QueryDict("", mutable=True)
        qd = self.update_query_dict(qd)
        return qd.urlencode()

    def count(self):
        """
        Return a count that takes into account the facet.
        """
        return self.stock_facet_qs.count()



class Process(object):

    """
    A helper class to group stocks for use in a view.
    """
    def __init__(self, slug, name, stocks):
        self.slug = slug
        self.name = name
        self.stock_lookup = {}
        facet_set = set()
        for stock in stocks:
            self.stock_lookup[stock.slug] = stock
            new_facets = []
            for facet_tuple in stock.facet_tuples:
                new_facets.append(facet_tuple[0])
            facet_set.update(new_facets)
        self.facets = sorted(facet_set, key=attrgetter("slug"))

    def all_stock_sequencers(self, facet_selection=None):
        # Get the facet select defined by the request.
        stock_seqs = []
        for stock in self.stock_lookup.values():
            stock_selection = StockSelection(self, stock=stock)
            stock_seqs.append(StockSequencer(stock_selection, facet_selection))
        return stock_seqs

    def stock_object_detail(self, request, queryset=None, object_id=None, slug=None,
        slug_field='slug', template_name=None, template_name_field=None,
        template_loader=loader, extra_context=None,
        context_processors=None, template_object_name='object',
        mimetype=None):
        """
        This is a wrapper around the generic object detail.

        It adds functionality to parse the get request query to determine the
        stock sequence and place it into the template's context. Also if the
        queryset is blank it will use the queryset from the stock with any
        facets applied.
        """
        stock_sel = StockSelection(self, request)
        facet_sel = FacetSelection(request)
        stock_seq =  StockSequencer(request=request, stock_selection=stock_sel,
                                    facet_selection=facet_sel)
        if queryset is None:
            queryset = stock_seq.stock_facet_qs
        if extra_context is None:
            extra_context = {}
        extra_context["stock_seq"] = stock_seq
        return object_detail(request, queryset, object_id, slug, slug_field,
                             template_name, template_name_field, template_loader,
                             extra_context, context_processors, template_object_name,
                             mimetype)

    def next_in_stock(self, request, current_object_id=None, current_slug=None,
                      slug_field=None, object_view=None, stop_iteration_view=None,
                      reverse_args=None, reverse_kwargs=None, stock_seq=None, is_forward=True):
        """
        Either an object_id or a slug and slug_field are required. This is used
        to check if the index needs to advance or not which happens if the
        current object is no longer part of the stock.

        The object_view and stop_iteration_view parameters are either view
        functios or strings as expected by urlresolvers.reverse. This function
        always results in a redirect. The object_view is used if there is a
        next object. Stop iteration view is used if there is no next object.
        The reverse_args and reverse_kwargs are passed through to the reverse
        call.

        The kwargs are adjusted to have the target object_id or slug.

        All GET query arguments are also passed through to the redirected view.
        """
        if stock_seq is None:
            stock_seq = self.sequencer(request)
        if reverse_kwargs is None:
            reverse_kwargs = {}
        view = object_view
        try:
            if is_forward:
                next_stock_seq = stock_seq.next()
            else:
                next_stock_seq = stock_seq.previous()
        except StopIteration:
            view = stop_iteration_view
        if current_object_id:
            reverse_kwargs["object_id"] = next_stock_seq.object_at_index.id
        elif current_slug:
            reverse_kwargs[slug_field] = next_stock_seq.object_at_index[slug_field]
        url = reverse(view, args=reverse_args, kwargs=reverse_kwargs)
        query_str = next_stock_seq.update_query_dict(request.GET.copy()).urlencode()
        if query_str:
            url += "?%s" % query_str
        return redirect(url)

# Wrap all the geckoboard views to catch an import error
# in case the django-geckoboard app is not installed.
try:
    from django_geckoboard.decorators import line_chart

    @line_chart
    def stock_line_chart(request, slug):
        """
        Feed a geckoboard line chart. The options that can be set in a GET
        query are points (integer), x_label (string), y_label (string), color
        (string).
        """
        points = int(request.GET.get("points", 50))
        x_label = request.GET.get("x_label", "")
        y_label = request.GET.get("y_label", slug.capitalize())
        color = request.GET.get("color", None)
        records = list(StockRecord.objects.filter(stock=slug).values_list('count', flat=True)[:points])
        records.reverse()
        if color: return ( records, x_label, y_label, color)
        return ( records, x_label, y_label)

except ImportError:
    pass

