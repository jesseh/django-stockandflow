"""
Create an additonal admin site for the Stocks and Flows. This lets us customize
it without interfering with the normal admin site. And we get a lot of free features
by levereging the admin code.

The functions are called during the Stock and Flow initialization to set up corresponding admin
models.
"""
from types import MethodType

from django.contrib import admin

class StockAndFlowAdminSite(admin.AdminSite):
    """
    A seperate admin site to handle stocks and flows.

    This leverages Django's fantastic built-in admin to offer great
    functionality for both stocks and flows. Via this interface the stocks and
    flows can be viewed and actions applied.

    The StockAndFlowAdminSite registers a proxy model for each stock and flow
    to get around the fact that the admin site does not like a givem model to
    be registered more than once.

    This stock and flow admin is meant to be registered as a seperate admin
    site so that it does not clutter up the normal admin with dynamically
    created stock and flow entries.
    """
    def __init__(self, *args):
        """
        Remove the delete_selected action because these are proxy models.
        The action can be added back in for a given model stock or flow.
        """
        super(StockAndFlowAdminSite, self). __init__(*args)
        self.disable_action('delete_selected')

    registration_sequence = 0
    def next_reg_sequence(self):
        """
        Assign a sequence number for registrations so that they can be ordered in the display
        """
        self.registration_sequence += 1
        return self.registration_sequence

    def register_stock(self, stock, admin_attributes={}, action_mixins=[]):
        proxy_model = self.create_proxy_model(stock, stock.queryset.model,
                                                      stock.queryset.model.__module__)
        model_admin = self.create_model_admin(stock, stock.queryset, admin_attributes,
                                                      action_mixins)
        self.register(proxy_model, model_admin)

    def register_flow(self, flow, admin_attributes={}, action_mixins=[]):
        default_attrs = { "readonly_fields": ("flow","source","sink","subject",),
                          "list_display": ("timestamp", "source", "sink","subject"),
                          "list_filter": ("source", "sink", "timestamp"),
                          "date_hierarchy": "timestamp",
                        }
        default_attrs.update(admin_attributes)
        proxy_model = self.create_proxy_model(flow, flow.flow_event_model,
                                              flow.subject_model.__module__)
        model_admin = self.create_model_admin(flow, flow.queryset, default_attrs,
                                              action_mixins)
        self.register(proxy_model, model_admin)


    def create_proxy_model(self, represents, base_model, module):
        """
        Create a proxy of a model that can be used to represents a stock or a flow in an
        admin site.

        Django requires that either the module or an app label be set, so adding the new 
        model to an existing module is necessary.
        """

        class_name = represents.__class__.__name__
        name = represents.name.title().replace(" ","") + class_name
        class Meta:
            proxy = True
            verbose_name_plural = "%02d. %s: %s" % (self.next_reg_sequence(), class_name, 
                                                  represents.name.capitalize())
        attrs = {
            '__module__': module,
            '__str__': represents.name,
            'Meta': Meta,
        }
        rv = type(name, (base_model,), attrs)
        return rv

    def create_model_admin(self, represents, queryset, attrs={}, action_mixins=[]):
        """
        Dynamically create an admin model class that can be registered in the
        admin site to represent a stock or flow.
        
         - The queryset extracts the records that are included in the stock or
           flow.
         - The attrs dict become the properties of the class.
         - The action_mixins provide the a way to include sets of admin actions
           in the resulting class.
        """

        class_name = represents.__class__.__name__
        name = represents.name.title().replace(" ","") + class_name + 'Admin'
        inherits = tuple([admin.ModelAdmin] + action_mixins)
        ret_class = type(name, inherits, attrs)
        ret_class.queryset = MethodType(lambda self, request: queryset, None, ret_class)
        # Block add and delete permissions because stocks and flows are read only
        ret_class.has_add_permission = MethodType(lambda self, request: False, None, ret_class)
        ret_class.has_delete_permission = MethodType(lambda self, request, obj=None: 
                                                     False, None, ret_class)

        # Collect all the mixed in actions
        all_actions = []
        reduce(lambda a, cls: a.extend(cls.actions), action_mixins, all_actions)
        ret_class.actions = all_actions
        ret_class.actions_on_bottom = True
        return ret_class
