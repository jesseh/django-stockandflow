from django.contrib.auth.models import User

from stockandflow.models import Facet

from profiles.models import Ramp, Source, PayState

coach = Facet(slug="coach", name="Coach", field_lookup="coach__username",
              values=User.objects.filter(groups__name="coach")
                         .values_list("username", flat=True))

ramp = Facet(slug="ramp", name="Ramp", field_lookup="ramp__name",
              values=Ramp.objects.all().values_list("name", flat=True))

source = Facet(slug="source", name="Source", field_lookup="source__name",
              values=Source.objects.all().values_list("name", flat=True))

pay_state = Facet(slug="pay_state", name="Pay state", field_lookup="pay_state__name",
              values=PayState.objects.all().values_list("name", flat=True))
