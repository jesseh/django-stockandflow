from django.conf.urls.defaults import *


urlpatterns = patterns("",
    url(r"^stock/line/(?P<slug>[-\w]+)/$", "stockandflow.views.stock_line_chart", name="stock_line_chart"),
)
