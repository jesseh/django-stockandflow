"""
Create a second admin site for the stocks and flows.
"""
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse

from stockandflow.admin import StockAndFlowAdminSite


site = StockAndFlowAdminSite("sfadmin")

