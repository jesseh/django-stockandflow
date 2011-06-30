from operator import attrgetter

from stockandflow.models import StockRecord

class Process(object):
    """
    A helper class to group stocks for use in a view.
    """
    def __init__(self, slug, name, stocks):
        self.slug = slug
        self.name = name
        self.stocks = stocks
        self.facets = self._get_all_facets()


    def _get_all_facets(self):
        facet_set = set()
        for stock in self.stocks:
            facet_set.update(stock.facets)
        return sorted(facet_set, key=attrgetter("slug"))

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

