# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'StockFacetRecord'
        db.create_table('stockandflow_stockfacetrecord', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('stock_record', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['stockandflow.StockRecord'])),
            ('facet', self.gf('django.db.models.fields.SlugField')(max_length=50, db_index=True)),
            ('value', self.gf('django.db.models.fields.CharField')(max_length=200, db_index=True)),
            ('count', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal('stockandflow', ['StockFacetRecord'])


    def backwards(self, orm):
        
        # Deleting model 'StockFacetRecord'
        db.delete_table('stockandflow_stockfacetrecord')


    models = {
        'stockandflow.periodicschedule': {
            'Meta': {'object_name': 'PeriodicSchedule'},
            'call_count': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'frequency': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_run_timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True'})
        },
        'stockandflow.stockfacetrecord': {
            'Meta': {'object_name': 'StockFacetRecord'},
            'count': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'facet': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'stock_record': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['stockandflow.StockRecord']"}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '200', 'db_index': 'True'})
        },
        'stockandflow.stockrecord': {
            'Meta': {'ordering': "['-timestamp']", 'object_name': 'StockRecord'},
            'count': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'stock': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'db_index': 'True'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['stockandflow']
