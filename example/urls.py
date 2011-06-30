from django.conf.urls.defaults import *

from processes import admin


urlpatterns = patterns("",
    url(r"^", include(admin.site.urls)),
)
