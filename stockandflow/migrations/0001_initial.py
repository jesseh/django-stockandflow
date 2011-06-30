# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'StockRecord'
        db.create_table('stockandflow_stockrecord', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('stock', self.gf('django.db.models.fields.SlugField')(max_length=50, db_index=True)),
            ('timestamp', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('count', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal('stockandflow', ['StockRecord'])

        # Adding model 'PeriodicSchedule'
        db.create_table('stockandflow_periodicschedule', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('frequency', self.gf('django.db.models.fields.SlugField')(max_length=50, db_index=True)),
            ('last_run_timestamp', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('call_count', self.gf('django.db.models.fields.IntegerField')(default=0, null=True)),
        ))
        db.send_create_signal('stockandflow', ['PeriodicSchedule'])


    def backwards(self, orm):
        
        # Deleting model 'StockRecord'
        db.delete_table('stockandflow_stockrecord')

        # Deleting model 'PeriodicSchedule'
        db.delete_table('stockandflow_periodicschedule')


    models = {
        'stockandflow.periodicschedule': {
            'Meta': {'object_name': 'PeriodicSchedule'},
            'call_count': ('django.db.models.fields.IntegerField', [], {'default': '0', 'null': 'True'}),
            'frequency': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_run_timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True'})
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
