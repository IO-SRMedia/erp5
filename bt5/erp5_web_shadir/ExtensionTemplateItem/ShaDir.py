##############################################################################
#
# Copyright (c) 20011 Nexedi SA and Contributors. All Rights Reserved.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################


import hashlib
import json
import validictory
from Products.ERP5Type.Document import newTempFile


def WebSection_getDocumentValue(self, key, portal=None, language=None,\
                                            validation_state=None, **kw):
  """
    API SHADIR

     - POST /<key>
        + parameters required:
           * file: the name of the file
           * urlmd5: mdsum of orginal url
           * sha512: the hash (sha512) of the file content

        + parameters not required:
           * valid-until: the date which the file must be expired
           * architecture: computer architecture

       Used to add information on shadir server.


     - GET /<key>
       Return list of information for a given key
       Raise HTTP error (404) if key does not exist
  """
  if portal is None:
    portal = self.getPortalObject()

  data_set = portal.portal_catalog.getResultValue(portal_type='Data Set',
                                                  reference=key)

  # Return the SIGNATURE file, if the document exists.
  if data_set is not None:
    document_list = [json.loads(document.getData()) \
                       for document in data_set.getFollowUpRelatedValueList()]

    temp_file = newTempFile(self, '%s.txt' % key)
    temp_file.setData(json.dumps(document_list))
    temp_file.setContentType('application/json')
    return temp_file.getObject()

  return None

def WebSection_setObject(self, id, ob, **kw):
  """
    Make any change related to the file uploaded.
  """
  portal = self.getPortalObject()

  data = self.REQUEST.get('BODY')
  schema = self.WebSite_getJSONSchema()
  structure = json.loads(data)
  validictory.validate(structure, schema)

  property_dict = structure[0]
  file_name = property_dict.get('file', None)
  ob.setFilename(file_name)

  expiration_date = property_dict.get('expiration_date', None)
  if expiration_date is not None:
    ob.setExpirationDate(expiration_date)

  ob.publishAlive()
  ob.setContentType('application/json')

  data_set = portal.portal_catalog.getResultValue(portal_type='Data Set',
                                                  reference=id)
  if data_set is None:
    data_set = portal.data_set_module.newContent(portal_type='Data Set',
                                                 reference=id)
    data_set.publish()
  ob.setFollowUp(data_set.getRelativeUrl())

  reference = hashlib.sha512(data).hexdigest()
  ob.setReference(reference)

  return ob
