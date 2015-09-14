#!usr/bin/env python
#  Author:
#  Muhammad Shahbaz (muhammad.shahbaz@gatech.edu)
#  Arpit Gupta (arpitg@cs.princeton.edu)

import os
from StringIO import StringIO
import globs
import socket,struct
from pymongo import MongoClient

def ip_to_long(ip):
	return struct.unpack('!L', socket.inet_aton(ip))[0]

class rib():

	def __init__(self,table_suffix,name,path):
		self.name = name + "_" + str(table_suffix)
		self.client = MongoClient(globs.MONGODB_HOST, globs.MONGODB_PORT)
		self.db = self.client['demo']
		self.session = self.db[self.name]

	def save_rib(self, path, outfile_name = "rib.db"):

		print "stub function"

	def __del__(self):
		#self.cluster.shutdown()
		pass

	def __setitem__(self,key,item):

		self.add(key,item)

	def __getitem__(self,key):

		return self.get(key)

	def add(self,key,item):

		key = str(key)
		if (isinstance(item,tuple) or isinstance(item,list)):
			assert (len(item) == 7)
			# Use cassandra session object
			in_stmt = {"prefix": key, "neighbor": item[0],
				"next_hop": item[1], "origin": item[2], 
				"as_path": item[3], "communities": item[4], 
				"med": item[5], "atomic_aggregate": item[6]}
			self.session.insert_one(in_stmt)

		elif (isinstance(item,dict) or isinstance(item,sqlite3.Row)):
			in_stmt = item
			in_stmt['prefix'] = key
			
			self.session.insert_one(in_stmt)
			#TODO: Add support for selective update

	def add_many(self,items):

		if (isinstance(items,list)):
			self.session.insert_many(items)

	def get_prefixes(self):
		rows = self.session.find()
		output_rows = []
		for row in rows:
			output_rows.append({"prefix": row['prefix']})
		return output_rows


	def get(self,key):

		key = str(key)
		rows = self.session.find({"prefix": key})
		output_rows = None

		if "input" in self.name:
			output_rows = []
			for row in rows:
				output_rows.append(row)		
		else:
			if rows.count() > 0:
				output_rows = rows[0]
		return output_rows

	def get_prefix_neighbor(self,key, neighbor):

		key = str(key)
		row = self.session.find_one({"prefix": key, "neighbor": neighbor})
		return row

	def get_all(self,key=None):

		rows = []
		if (key is not None):
			rows = self.session.find({"prefix": key})
		else:
			rows = self.session.find()
		output_rows = None

		if "input" in self.name:
			output_rows = []
			for row in rows:
                                output_rows.append(row)
		else:
			if len(rows) > 0:
				output_rows = rows[0]

		return output_rows

	def filter(self,item,value):

		rows = self.session.find_one({item: value})
		return rows

	def update(self,key,item,value):
		
		rows = self.session.update_one({"prefix": key},{"$set":{ item: value}})
	
	def delete(self,key):

		# TODO: Add more granularity in the delete process i.e., instead of just prefix,
		# it should be based on a conjunction of other attributes too.
		rows = self.session.delete_many({"prefix": key})

	def delete_prefix_neighbor(self, prefix, neighbor):

		# Deleting one entry in prefix's column that matches on neighbor
		rows = self.session.delete_one({"prefix": prefix, "neighbor": neighbor})

	def delete_all(self):
		rows = self.session.delete_many()

	def commit(self):
		pass
		#print "previous commit, does nothing"

	def rollback(self):

		print "previous rollback, does nothing"


''' main '''
if __name__ == '__main__':

	#TODO Update test

	myrib = rib('ashello', 'test', False)
	print type(myrib)
	#(prefix, neighbor, next_hop, origin, as_path, communities, med,atomic_aggregate)
	myrib['100.0.0.1/16'] = ('172.0.0.2','172.0.0.2', 'igp', '100, 200, 300', '0', 0,'false')
	#myrib['100.0.0.1/16'] = ['172.0.0.2', 'igp', '100, 200, 300', '0', 'false']
	#myrib['100.0.0.1/16'] = {'next_hop':'172.0.0.2', 'origin':'igp', 'as_path':'100, 200, 300',
	#                          'med':'0', 'atomic_aggregate':'false'}
	myrib.commit()

	myrib.update('100.0.0.1/16', 'next_hop', '190.0.0.2')
	myrib.commit()

	val = myrib.filter('prefix', '100.0.0.1/16')
	print val
	print val['next_hop']
	val2 = myrib.get_prefix_neighbor('100.0.0.1/16', '172.0.0.2')
	print val2
