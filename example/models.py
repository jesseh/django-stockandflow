from django.db import models

from django.contrib.auth.models import User

from stockandflow.models import FlowEventModel

from profiles.models import Profile


class ProfileFlowEvent(FlowEventModel):
    subject = models.ForeignKey(Profile, related_name="flow_event")

class UserFlowEvent(FlowEventModel):
    subject = models.ForeignKey(User, related_name="flow_event")


#import to get stocks and flow registered
import processes.stocksandflows.profiles_sandf
import processes.stocksandflows.user_sandf
