# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2004 Nexedi SARL and Contributors. All Rights Reserved.
#          Sebastien Robin <seb@nexedi.com>
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
##############################################################################

import unittest
from Testing import ZopeTestCase
from Products.ERP5Type.tests.runUnitTest import tests_home
from Products.ERP5Type.tests.ERP5TypeTestCase import ERP5TypeTestCase
from AccessControl.SecurityManagement import newSecurityManager
from Products.ERP5SyncML.Conduit.ERP5Conduit import ERP5Conduit
from Products.ERP5SyncML.SyncCode import SyncCode
from zLOG import LOG
from base64 import b64encode, b64decode, b16encode, b16decode
import transaction
from ERP5Diff import ERP5Diff
from lxml import etree


class TestERP5SyncMLMixin:

  # Different variables used for this test
  workflow_id = 'edit_workflow'
  first_name1 = 'Sebastien'
  last_name1 = 'Robin'
  # At the beginning, I was using iso-8859-15 strings, but actually
  # erp5 is using utf-8 everywhere
  #description1 = 'description1 --- $sdfrç_sdfsçdf_oisfsopf'
  description1 = 'description1 --- $sdfr\xc3\xa7_sdfs\xc3\xa7df_oisfsopf'
  lang1 = 'fr'
  format2 = 'html'
  format3 = 'xml'
  format4 = 'txt'
  first_name2 = 'Jean-Paul'
  last_name2 = 'Smets'
  #description2 = 'description2éà@  $*< <<<  ----- >>>></title>&oekd'
  description2 = 'description2\xc3\xa9\xc3\xa0@  $*< <<<  ----- >>>></title>&oekd'
  lang2 = 'en'
  first_name3 = 'Yoshinori'
  last_name3 = 'Okuji'
  #description3 = 'description3 çsdf__sdfççç_df___&&é]]]°°°°°°'
  description3 = 'description3 \xc3\xa7sdf__sdf\xc3\xa7\xc3\xa7\xc3\xa7_df___&&\xc3\xa9]]]\xc2\xb0\xc2\xb0\xc2\xb0\xc2\xb0\xc2\xb0\xc2\xb0'
  #description4 = 'description4 sdflkmooo^^^^]]]]]{{{{{{{'
  description4 = 'description4 sdflkmooo^^^^]]]]]{{{{{{{'
  lang3 = 'jp'
  lang4 = 'ca'
  xml_mapping = 'asXML'
  id1 = '170'
  id2 = '171'
  pub_id = 'Publication'
  sub_id1 = 'Subscription1'
  sub_id2 = 'Subscription2'
  nb_subscription = 2
  nb_publication = 1
  nb_synchronization = 3
  nb_message_first_synchronization = 10
  nb_message_first_sync_max_lines = 10
  _subscription_url1 = tests_home + '/sync_client1'
  _subscription_url2 = tests_home + '/sync_client2'
  _publication_url = tests_home + '/sync_server'
  # XXX Why the prefix is not 'file://' ? This is inconsistent with urlopen:
  #     urlopen('file://tmp/foo') -> ERROR
  #     urlopen('file:///tmp/foo') -> OK
  subscription_url1 = 'file:/' + _subscription_url1
  subscription_url2 = 'file:/' + _subscription_url2
  publication_url = 'file:/' + _publication_url
  activity_enabled = False
  #publication_url = 'server@localhost'
  #subscription_url1 = 'client1@localhost'
  #subscription_url2 = 'client2@localhost'


  def afterSetUp(self):
    """Setup."""
    self.login()
    # This test creates Person inside Person, so we modifiy type information to
    # allow anything inside Person (we'll cleanup on teardown)
    self.getTypesTool().getTypeInfo('Person').filter_content_types = 0

  def beforeTearDown(self):
    """Clean up."""
    # type informations
    self.getTypesTool().getTypeInfo('Person').filter_content_types = 1

  def getBusinessTemplateList(self):
    """
      Return the list of business templates.

      the business template sync_crm give 3 folders:
      /person_server 
      /person_client1 : empty
      /person_client2 : empty
    """
    return ('erp5_base',)

  def getSynchronizationTool(self):
    return getattr(self.getPortal(), 'portal_synchronizations', None)

  def getPersonClient1(self):
    return getattr(self.getPortal(), 'person_client1', None)

  def getPersonServer(self):
    return getattr(self.getPortal(), 'person_server', None)

  def getPersonClient2(self):
    return getattr(self.getPortal(), 'person_client2', None)

  def getPortalId(self):
    return self.getPortal().getId()

  def login(self, quiet=0):
    uf = self.getPortal().acl_users
    uf._doAddUser('fab', 'myPassword', ['Manager'], [])
    uf._doAddUser('ERP5TypeTestCase', '', ['Manager'], [])
    uf._doAddUser('syncml', '', ['Manager'], [])
    user = uf.getUserById('fab').__of__(uf)
    newSecurityManager(None, user)
  
  def initPersonModule(self, quiet=0, run=0):
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Init Person Module')
      LOG('Testing... ',0,'initPersonModule')
    self.login()
    portal = self.getPortal()
    if not hasattr(portal,'person_server'):
      portal.portal_types.constructContent(type_name = 'Person Module',
                                           container = portal,
                                           id = 'person_server')
    if not hasattr(portal,'person_client1'):
      portal.portal_types.constructContent(type_name = 'Person Module',
                                           container = portal,
                                           id = 'person_client1')
    if not hasattr(portal,'person_client2'):
      portal.portal_types.constructContent(type_name = 'Person Module',
                                           container = portal,
                                           id = 'person_client2')

  def populatePersonServer(self, quiet=0, run=0):
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Populate Person Server ')
      LOG('Testing... ',0,'populatePersonServer')
    self.login()
    portal = self.getPortal()
    self.initPersonModule(quiet=1, run=1)
    person_server = self.getPersonServer()
    person1 = person_server.newContent(id=self.id1, portal_type='Person')
    kw = {'first_name':self.first_name1,'last_name':self.last_name1,
          'description':self.description1}
    person1.edit(**kw)
    person2 = person_server.newContent(id=self.id2, portal_type='Person')
    kw = {'first_name':self.first_name2,'last_name':self.last_name2,
          'description':self.description2}
    person2.edit(**kw)
    nb_person = len(person_server.objectValues())
    self.assertEqual(nb_person, 2)
    return nb_person

  def populatePersonClient1(self, quiet=0, run=0):
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Populate Person Client 1 ')
      LOG('Testing... ',0,'populatePersonClient1')
    self.login()
    portal = self.getPortal()
    self.initPersonModule(quiet=1, run=1)
    person_client = self.getPersonClient1()
    for id in range(1, 60):
      person = person_client.newContent(id=id, portal_type='Person')
      kw = {'first_name':self.first_name1,'last_name':self.last_name1,
            'description':self.description1}
      person.edit(**kw)
    nb_person = len(person_client.objectValues())
    self.assertEqual(nb_person,59)
    return nb_person

  def synchronize(self, id, run=1):
    """
    This just define how we synchronize, we have
    to define it here because it is specific to the unit testing
    """
    portal_sync = self.getSynchronizationTool()
    subscription = portal_sync.getSubscription(id)
    publication = None
    for pub in portal_sync.getPublicationList():
      if pub.getPublicationUrl()==subscription.getPublicationUrl():
        publication = pub
    self.assertTrue(publication is not None)
    # reset files, because we do sync by files
    file = open(self._subscription_url1, 'w')
    file.write('')
    file.close()
    file = open(self._subscription_url2, 'w')
    file.write('')
    file.close()
    file = open(self._publication_url, 'w')
    file.write('')
    file.close()
    nb_message = 1
    result = portal_sync.SubSync(subscription.getPath())
    while result['has_response']==1:
      portal_sync.PubSync(publication.getPath())
      if self.activity_enabled:
        transaction.commit()
        self.tic()
      result = portal_sync.SubSync(subscription.getPath())
      if self.activity_enabled:
        transaction.commit()
        self.tic()
      nb_message += 1 + result['has_response']
    return nb_message

  def synchronizeWithBrokenMessage(self, id, run=1):
    """
    This just define how we synchronize, we have
    to define it here because it is specific to the unit testing
    """
    portal_sync = self.getSynchronizationTool()
    #portal_sync.email = None # XXX To be removed
    subscription = portal_sync.getSubscription(id)
    publication = None
    for pub in portal_sync.getPublicationList():
      if pub.getPublicationUrl()==subscription.getPublicationUrl():
        publication = pub
    self.assertTrue(publication is not None)
    # reset files, because we do sync by files
    file = open(self._subscription_url1, 'w')
    file.write('')
    file.close()
    file = open(self._subscription_url2, 'w')
    file.write('')
    file.close()
    file = open(self._publication_url, 'w')
    file.write('')
    file.close()
    nb_message = 1
    result = portal_sync.SubSync(subscription.getPath())
    while result['has_response']==1:
      # We do thing three times, so that we will test
      # if we manage well duplicate messages
      portal_sync.PubSync(publication.getPath())
      if self.activity_enabled:
        transaction.commit()
        self.tic()
      portal_sync.PubSync(publication.getPath())
      if self.activity_enabled:
        transaction.commit()
        self.tic()
      portal_sync.PubSync(publication.getPath())
      if self.activity_enabled:
        transaction.commit()
        self.tic()
      result = portal_sync.SubSync(subscription.getPath())
      if self.activity_enabled:
        transaction.commit()
        self.tic()
      result = portal_sync.SubSync(subscription.getPath())
      if self.activity_enabled:
        transaction.commit()
        self.tic()
      result = portal_sync.SubSync(subscription.getPath())
      if self.activity_enabled:
        transaction.commit()
        self.tic()
      nb_message += 1 + result['has_response']
    return nb_message

  def checkSynchronizationStateIsSynchronized(self, quiet=0, run=1):
    portal_sync = self.getSynchronizationTool()
    person_server = self.getPersonServer()
    for person in person_server.objectValues():
      state_list = portal_sync.getSynchronizationState(person)
      for state in state_list:
        self.assertEqual(state[1], state[0].SYNCHRONIZED)
    person_client1 = self.getPersonClient1()
    for person in person_client1.objectValues():
      state_list = portal_sync.getSynchronizationState(person)
      for state in state_list:
        self.assertEqual(state[1], state[0].SYNCHRONIZED)
    person_client2 = self.getPersonClient2()
    for person in person_client2.objectValues():
      state_list = portal_sync.getSynchronizationState(person)
      for state in state_list:
        self.assertEqual(state[1], state[0].SYNCHRONIZED)
    # Check for each signature that the tempXML is None
    for sub in portal_sync.getSubscriptionList():
      for m in sub.getSignatureList():
        self.assertEquals(m.getTempXML(),None)
        self.assertEquals(m.getPartialXML(),None)
    for pub in portal_sync.getPublicationList():
      for sub in pub.getSubscriberList():
        for m in sub.getSignatureList():
          self.assertEquals(m.getPartialXML(),None)

  def verifyFirstNameAndLastNameAreNotSynchronized(self, first_name, 
      last_name, person_server, person_client):
    """
      verify that the first and last name are NOT synchronized
    """
    self.assertNotEqual(person_server.getFirstName(), first_name)
    self.assertNotEqual(person_server.getLastName(), last_name)
    self.assertEqual(person_client.getFirstName(), first_name)
    self.assertEqual(person_client.getLastName(), last_name)

  def checkFirstSynchronization(self, id=None, nb_person=0):

    portal_sync = self.getSynchronizationTool()
    subscription1 = portal_sync.getSubscription(self.sub_id1)
    subscription2 = portal_sync.getSubscription(self.sub_id2)
    self.assertEqual(len(subscription1.getObjectList()), nb_person)
    person_server = self.getPersonServer() # We also check we don't
                                           # modify initial ob
    person1_s = person_server._getOb(self.id1)
    self.assertEqual(person1_s.getId(), self.id1)
    self.assertEqual(person1_s.getFirstName(), self.first_name1)
    self.assertEqual(person1_s.getLastName(), self.last_name1)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(id)
    self.assertEqual(person1_c.getId(), id)
    self.assertEqual(person1_c.getFirstName(), self.first_name1)
    self.assertEqual(person1_c.getLastName(), self.last_name1)
    self.assertEqual(len(subscription2.getObjectList()), nb_person)
    person_client2 = self.getPersonClient2()
    person2_c = person_client2._getOb(id) 
    self.assertEqual(person2_c.getId(), id)
    self.assertEqual(person2_c.getFirstName(), self.first_name1)
    self.assertEqual(person2_c.getLastName(), self.last_name1)
  
  def resetSignaturePublicationAndSubscription(self):
    portal_sync = self.getSynchronizationTool()
    publication = portal_sync.getPublication(self.pub_id)
    subscription1 = portal_sync.getSubscription(self.sub_id1)
    subscription2 = portal_sync.getSubscription(self.sub_id2)
    publication.resetAllSubscribers()
    subscription1.resetAllSignatures()
    transaction.commit()
    self.tic()

  def assertXMLViewIsEqual(self, sub_id, object_pub=None, object_sub=None,
                                                                  force=False):
    """
      Check the equality between two xml objects with gid as id
    """
    portal_sync = self.getSynchronizationTool()
    subscription = portal_sync.getSubscription(sub_id)
    publication = portal_sync.getPublication(self.pub_id)
    gid_pub = publication.getGidFromObject(object_pub)
    gid_sub = publication.getGidFromObject(object_sub)
    self.assertEqual(gid_pub, gid_sub)
    conduit = ERP5Conduit()
    xml_pub = conduit.getXMLFromObjectWithGid(object=object_pub, gid=gid_pub,
                                       xml_mapping=publication.getXMLMapping())
    #if One Way From Server there is not xml_mapping for subscription
    xml_sub = conduit.getXMLFromObjectWithGid(object=object_sub, gid=gid_sub,
                                 xml_mapping=subscription.getXMLMapping(force))
    erp5diff = ERP5Diff()
    erp5diff.compare(xml_pub, xml_sub)
    result = erp5diff.outputString()
    result = etree.XML(result)
    identity = True
    for update in result:
      #XXX edit workflow is not replaced, so discard workflow checking
      select = update.get('select', '')
      discarded_list = ('edit_workflow',)
      if 'edit_workflow' in  select:
        continue
      else:
        identity = False
        break
    if not identity:
      self.fail('diff between pub:%s and sub:%s \n%s' % (object_pub.getPath(),
                                                         object_sub.getPath(),
                                   etree.tostring(result, pretty_print=True)))

  def deletePublicationAndSubscription(self):
    portal_sync = self.getSynchronizationTool()
    portal_sync.manage_deletePublication(title=self.pub_id)
    portal_sync.manage_deleteSubscription(title=self.sub_id1)
    if portal_sync.getSubscription(title=self.sub_id2):
      portal_sync.manage_deleteSubscription(title=self.sub_id2)

class TestERP5SyncML(TestERP5SyncMLMixin, ERP5TypeTestCase):
  
  run_all_test = True
  def getTitle(self):
    """
    """
    return "ERP5 SyncML"

  def setupPublicationAndSubscription(self, quiet=0, run=run_all_test):
    portal_sync = self.getSynchronizationTool()
    person_server = self.getPersonServer()
    if person_server is not None:
      portal = self.getPortal()
      portal._delObject(id='person_server')
      portal._delObject(id='person_client1')
      portal._delObject(id='person_client2')
      self.deletePublicationAndSubscription()
    self.test_02_AddPublication(quiet=1,run=1)
    self.test_03_AddSubscription1(quiet=1,run=1)
    self.test_04_AddSubscription2(quiet=1,run=1)
      
  def setupPublicationAndSubscriptionAndGid(self, quiet=0, run=run_all_test):
    self.setupPublicationAndSubscription(quiet=1,run=1)
    portal_sync = self.getSynchronizationTool()
    sub1 = portal_sync.getSubscription(self.sub_id1)
    sub2 = portal_sync.getSubscription(self.sub_id2)
    pub = portal_sync.getPublication(self.pub_id)
    sub1.setConduit('ERP5ConduitTitleGid')
    sub2.setConduit('ERP5ConduitTitleGid')
    pub.setConduit('ERP5ConduitTitleGid')
    pub.setSynchronizationIdGenerator('_generateNextId')
    sub1.setSynchronizationIdGenerator('_generateNextId')
    sub2.setSynchronizationIdGenerator('_generateNextId')

  def checkSynchronizationStateIsConflict(self, quiet=0, run=1):
    portal_sync = self.getSynchronizationTool()
    person_server = self.getPersonServer()
    for person in person_server.objectValues():
      if person.getId()==self.id1:
        state_list = portal_sync.getSynchronizationState(person)
        for state in state_list:
          self.assertEqual(state[1], state[0].CONFLICT)
    person_client1 = self.getPersonClient1()
    for person in person_client1.objectValues():
      if person.getId()==self.id1:
        state_list = portal_sync.getSynchronizationState(person)
        for state in state_list:
          self.assertEqual(state[1], state[0].CONFLICT)
    person_client2 = self.getPersonClient2()
    for person in person_client2.objectValues():
      if person.getId()==self.id1:
        state_list = portal_sync.getSynchronizationState(person)
        for state in state_list:
          self.assertEqual(state[1], state[0].CONFLICT)
    # make sure sub object are also in a conflict mode
    person = person_client1._getOb(self.id1)
    # use a temp_object to create a no persistent object in person
    sub_person =\
    person.newContent(id=self.id1, portal_type='Person', temp_object=1)
    state_list = portal_sync.getSynchronizationState(sub_person)
    for state in state_list:
      self.assertEqual(state[1], state[0].CONFLICT)
  
  def populatePersonServerWithSubObject(self, quiet=0, run=run_all_test):
    """
    Before this method, we need to call populatePersonServer
    Then it will give the following tree :
    - person_server :
      - id1
        - id1
          - id2
          - id1
      - id2
    """
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Populate Person Server With Sub Object ')
      LOG('Testing... ',0,'populatePersonServerWithSubObject')
    person_server = self.getPersonServer()
    person1 = person_server._getOb(self.id1)
    sub_person1 = person1.newContent(id=self.id1, portal_type='Person')
    kw = {'first_name':self.first_name1,'last_name':self.last_name1,
        'description':self.description1}
    sub_person1.edit(**kw)
    sub_sub_person1 = sub_person1.newContent(id=self.id1, portal_type='Person')
    kw = {'first_name':self.first_name1,'last_name':self.last_name1,
        'description':self.description1, 'default_telephone_text':'0689778308'}
    sub_sub_person1.edit(**kw)
    sub_sub_person2 = sub_person1.newContent(id=self.id2, portal_type='Person')
    kw = {'first_name':self.first_name2,'last_name':self.last_name2,
          'description':self.description2}
    sub_sub_person2.edit(**kw)
    # remove ('','portal...','person_server')
    len_path = len(sub_sub_person1.getPhysicalPath()) - 3 
    self.assertEqual(len_path, 3)
    len_path = len(sub_sub_person2.getPhysicalPath()) - 3 
    self.assertEqual(len_path, 3)

  def addAuthenticationToPublication(self, publication_id, login, password, 
      auth_format, auth_type):
    """
      add authentication to the publication
    """
    portal_sync = self.getSynchronizationTool()
    pub = portal_sync.getPublication(publication_id)
    pub.setLogin(login)
    pub.setPassword(password)
    pub.setAuthenticationFormat(auth_format)
    pub.setAuthenticationType(auth_type)


  def addAuthenticationToSubscription(self, subscription_id, login, password, 
      auth_format, auth_type):
    """
      add authentication to the subscription
    """
    portal_sync = self.getSynchronizationTool()
    sub = portal_sync.getSubscription(subscription_id)
    sub.setAuthenticated(False)
    sub.setLogin(login)
    sub.setPassword(password)
    sub.setAuthenticationFormat(auth_format)
    sub.setAuthenticationType(auth_type)


  def test_01_HasEverything(self, quiet=0, run=run_all_test):
    # Test if portal_synchronizations was created
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Has Everything ')
      LOG('Testing... ',0,'test_01_HasEverything')
    self.assertNotEqual(self.getSynchronizationTool(), None)
    #self.failUnless(self.getPersonServer()!=None)
    #self.failUnless(self.getPersonClient1()!=None)
    #self.failUnless(self.getPersonClient2()!=None)

  def test_02_AddPublication(self, quiet=0, run=run_all_test):
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Add a Publication ')
      LOG('Testing... ',0,'test_02_AddPublication')
    portal_id = self.getPortalName()
    portal_sync = self.getSynchronizationTool()
    if portal_sync.getPublication(self.pub_id) is not None:
      portal_sync.manage_deletePublication(title=self.pub_id)
    portal_sync.manage_addPublication(title=self.pub_id,
        publication_url=self.publication_url, 
        destination_path='/%s/person_server' % portal_id, 
        source_uri='Person', 
        query='objectValues', 
        xml_mapping=self.xml_mapping, 
        conduit='ERP5Conduit',
        gpg_key='',
        activity_enabled=self.activity_enabled,
        authentication_format='b64',
        authentication_type='syncml:auth-basic')
    pub = portal_sync.getPublication(self.pub_id)
    self.failUnless(pub is not None)

  def test_03_AddSubscription1(self, quiet=0, run=run_all_test):
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Add First Subscription ')
      LOG('Testing... ',0,'test_03_AddSubscription1')
    portal_id = self.getPortalId()
    portal_sync = self.getSynchronizationTool()
    if portal_sync.getSubscription(self.sub_id1) is not None:
      portal_sync.manage_deleteSubscription(title=self.sub_id1)
    portal_sync.manage_addSubscription(title=self.sub_id1, 
        publication_url=self.publication_url,
        subscription_url=self.subscription_url1, 
        destination_path='/%s/person_client1' % portal_id,
        source_uri='Person', 
        target_uri='Person', 
        query='objectValues', 
        xml_mapping=self.xml_mapping, 
        conduit='ERP5Conduit', 
        gpg_key='',
        activity_enabled=self.activity_enabled,
        login='fab',
        password='myPassword')
    sub = portal_sync.getSubscription(self.sub_id1)
    self.failUnless(sub is not None)

  def test_04_AddSubscription2(self, quiet=0, run=run_all_test):
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Add Second Subscription ')
      LOG('Testing... ',0,'test_04_AddSubscription2')
    portal_id = self.getPortalId()
    portal_sync = self.getSynchronizationTool()
    if portal_sync.getSubscription(self.sub_id2) is not None:
      portal_sync.manage_deleteSubscription(title=self.sub_id2)
    portal_sync.manage_addSubscription(title=self.sub_id2, 
        publication_url=self.publication_url,
        subscription_url=self.subscription_url2, 
        destination_path='/%s/person_client2' % portal_id,
        source_uri='Person', 
        target_uri='Person', 
        query='objectValues', 
        xml_mapping=self.xml_mapping, 
        conduit='ERP5Conduit', 
        gpg_key='',
        activity_enabled=self.activity_enabled,
        login='fab',
        password='myPassword')
    sub = portal_sync.getSubscription(self.sub_id2)
    self.failUnless(sub is not None)

  def test_05_GetSynchronizationList(self, quiet=0, run=run_all_test):
    # This test the getSynchronizationList, ie,
    # We want to see if we retrieve both the subscription
    # and the publication
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest getSynchronizationList ')
      LOG('Testing... ',0,'test_05_GetSynchronizationList')
    self.setupPublicationAndSubscription(quiet=1,run=1)
    portal_sync = self.getSynchronizationTool()
    synchronization_list = portal_sync.getSynchronizationList()
    self.assertEqual(len(synchronization_list), self.nb_synchronization)

  def test_06_GetObjectList(self, quiet=0, run=run_all_test):
    """
    This test the default getObjectList, ie, when the
    query is 'objectValues', and this also test if we enter
    a new method for the query
    """
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest getObjectList ')
      LOG('Testing... ',0,'test_06_GetObjectList')
    self.login()
    self.setupPublicationAndSubscription(quiet=1,run=1)
    nb_person = self.populatePersonServer(quiet=1,run=1)
    portal_sync = self.getSynchronizationTool()
    publication_list = portal_sync.getPublicationList()
    publication = publication_list[0]
    object_list = publication.getObjectList()
    self.assertEqual(len(object_list), nb_person)
    # now try to set a different method for query
    def query(object):
      object_list = object.objectValues()
      return_list = []
      for o in object_list:
        if o.getId()==self.id1:
          return_list.append(o)
      return return_list
    publication.setQuery(query)
    object_list = publication.getObjectList()
    self.assertEqual(len(object_list), 1)
    # Add the query path
    portal_id = self.getPortalName()
    publication.setDestinationPath('/%s/' % portal_id)
    publication.setQuery('person_server/objectValues')
    object_list = publication.getObjectList()
    self.assertEqual(len(object_list), nb_person)

  def test_07_ExportImport(self, quiet=0, run=run_all_test):
    """
    We will try to export a person with asXML
    And then try to add it to another folder with a conduit
    """
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Export and Import ')
      LOG('Testing... ',0,'test_07_ExportImport')
    self.login()
    self.populatePersonServer(quiet=1,run=1)
    person_server = self.getPersonServer()
    person_client1 = self.getPersonClient1()
    person = person_server._getOb(self.id1)
    xml_output = person.asXML()
    conduit = ERP5Conduit()
    conduit.addNode(object=person_client1,xml=xml_output)
    self.assertEqual(len(person_client1.objectValues()), 1)
    new_object = person_client1._getOb(self.id1)
    self.assertEqual(new_object.getLastName(), self.last_name1)
    self.assertEqual(new_object.getFirstName(), self.first_name1)
    # XXX We should also looks at the workflow history
    self.assertEqual(len(new_object.workflow_history[self.workflow_id]), 2)
    s_local_role = person_server.get_local_roles()
    c_local_role = person_client1.get_local_roles()
    self.assertEqual(s_local_role,c_local_role)

  def test_08_FirstSynchronization(self, quiet=0, run=run_all_test):
    # We will try to populate the folder person_client1
    # with the data form person_server
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest First Synchronization ')
      LOG('Testing... ',0,'test_08_FirstSynchronization')
    self.login()
    self.setupPublicationAndSubscription(quiet=1, run=1)
    nb_person = self.populatePersonServer(quiet=1, run=1)
    portal_sync = self.getSynchronizationTool()
    for sub in portal_sync.getSubscriptionList():
      self.assertEquals(sub.getSynchronizationType(), SyncCode.SLOW_SYNC)
    # Synchronize the first client
    nb_message1 = self.synchronize(self.sub_id1)
    for sub in portal_sync.getSubscriptionList():
      if sub.getTitle() == self.sub_id1:
        self.assertEquals(sub.getSynchronizationType(), SyncCode.TWO_WAY)
      else:
        self.assertEquals(sub.getSynchronizationType(), SyncCode.SLOW_SYNC)
    self.assertEqual(nb_message1, self.nb_message_first_synchronization)
    # Synchronize the second client
    nb_message2 = self.synchronize(self.sub_id2)
    for sub in portal_sync.getSubscriptionList():
      self.assertEquals(sub.getSynchronizationType(), SyncCode.TWO_WAY)
    self.assertEqual(nb_message2, self.nb_message_first_synchronization)
    self.checkFirstSynchronization(id=self.id1, nb_person=nb_person)

  def test_09_FirstSynchronizationWithLongLines(self, quiet=0, run=run_all_test):
    # We will try to populate the folder person_client1
    # with the data form person_server
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest First Synchronization With Long Lines ')
      LOG('Testing... ',0,'test_09_FirstSynchronizationWithLongLines')
    self.login()
    self.setupPublicationAndSubscription(quiet=1,run=1)
    nb_person = self.populatePersonServer(quiet=1,run=1)
    person_server = self.getPersonServer()
    long_line = 'a' * 10000 + ' --- '
    person1_s = person_server._getOb(self.id1)
    kw = {'first_name':long_line} 
    person1_s.edit(**kw)
    # Synchronize the first client
    nb_message1 = self.synchronize(self.sub_id1)
    self.assertEqual(nb_message1, self.nb_message_first_synchronization)
    portal_sync = self.getSynchronizationTool()
    subscription1 = portal_sync.getSubscription(self.sub_id1)
    self.assertEqual(len(subscription1.getObjectList()), nb_person)
    self.assertEqual(person1_s.getId(), self.id1)
    self.assertEqual(person1_s.getFirstName(), long_line)
    self.assertEqual(person1_s.getLastName(), self.last_name1)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)

  def test_10_GetObjectFromGid(self, quiet=0, run=run_all_test):
    # We will try to get an object from a publication
    # just by givin the gid
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest getObjectFromGid ')
      LOG('Testing... ',0,'test_10_GetObjectFromGid')
    self.login()
    self.setupPublicationAndSubscription(quiet=1,run=1)
    self.populatePersonServer(quiet=1,run=1)
    # By default we can just give the id
    portal_sync = self.getSynchronizationTool()
    publication = portal_sync.getPublication(self.pub_id)
    object = publication.getObjectFromId(self.id1)
    self.failUnless(object is not None)
    self.assertEqual(object.getId(), self.id1)

  def test_11_GetSynchronizationState(self, quiet=0, run=run_all_test):
    # We will try to get the state of objects
    # that are just synchronized,
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest getSynchronizationState ')
      LOG('Testing... ',0,'test_11_GetSynchronizationState')
    self.test_08_FirstSynchronization(quiet=1,run=1)
    portal_sync = self.getSynchronizationTool()
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    state_list_s = portal_sync.getSynchronizationState(person1_s)
    self.assertEqual(len(state_list_s), self.nb_subscription) # one state
                                                  # for each subscriber
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    state_list_c = portal_sync.getSynchronizationState(person1_c)
    self.assertEqual(len(state_list_c), 1) # one state
                                        # for each subscriber
    self.checkSynchronizationStateIsSynchronized()

  def test_12_UpdateSimpleData(self, quiet=0, run=run_all_test):
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Update Simple Data ')
      LOG('Testing... ',0,'test_12_UpdateSimpleData')
    self.test_08_FirstSynchronization(quiet=1,run=1)
    # First we do only modification on server
    portal_sync = self.getSynchronizationTool()
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    kw = {'first_name':self.first_name3,'last_name':self.last_name3}
    person1_s.edit(**kw)
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    self.assertEqual(person1_s.getFirstName(), self.first_name3)
    self.assertEqual(person1_s.getLastName(), self.last_name3)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    # Then we do only modification on a client
    kw = {'first_name':self.first_name1,'last_name':self.last_name1}
    person1_c.edit(**kw)
    #person1_c.setModificationDate(DateTime()+1)
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    #person1_s = person_server._getOb(self.id1)
    self.assertEqual(person1_s.getFirstName(), self.first_name1)
    self.assertEqual(person1_s.getLastName(), self.last_name1)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    # Then we do only modification on both the client and the server
    # and of course, on the same object
    kw = {'first_name':self.first_name3}
    person1_s.edit(**kw)
    kw = {'description':self.description3}
    person1_c.edit(**kw)
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    #person1_s = person_server._getOb(self.id1)
    self.assertEqual(person1_s.getFirstName(), self.first_name3)
    self.assertEqual(person1_s.getDescription(), self.description3)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)

  def test_13_GetConflictList(self, quiet=0, run=run_all_test):
    # We will try to generate a conflict and then to get it
    # We will also make sure it contains what we want
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Get Conflict List ')
      LOG('Testing... ',0,'test_13_GetConflictList')
    self.test_08_FirstSynchronization(quiet=1,run=1)
    # First we do only modification on server
    portal_sync = self.getSynchronizationTool()
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    person1_s.setDescription(self.description2)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    person1_c.setDescription(self.description3)
    self.synchronize(self.sub_id1)
    conflict_list = portal_sync.getConflictList()
    self.assertEqual(len(conflict_list), 1)
    conflict = conflict_list[0]
    self.assertEqual(person1_c.getDescription(), self.description3)
    self.assertEqual(person1_s.getDescription(), self.description2)
    self.assertEqual(conflict.getPropertyId(), 'description')
    self.assertEqual(conflict.getPublisherValue(), self.description2)
    self.assertEqual(conflict.getSubscriberValue(), self.description3)
    subscriber = conflict.getSubscriber()
    self.assertEqual(subscriber.getSubscriptionUrl(), self.subscription_url1)

  def test_14_GetPublisherAndSubscriberDocument(self, quiet=0, run=run_all_test):
    # We will try to generate a conflict and then to get it
    # We will also make sure it contains what we want
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Get Publisher And Subscriber Document ')
      LOG('Testing... ',0,'test_14_GetPublisherAndSubscriberDocument')
    self.test_13_GetConflictList(quiet=1,run=1)
    # First we do only modification on server
    portal_sync = self.getSynchronizationTool()
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    conflict_list = portal_sync.getConflictList()
    conflict = conflict_list[0]
    publisher_document = conflict.getPublisherDocument()
    self.assertEqual(publisher_document.getDescription(), self.description2)
    subscriber_document = conflict.getSubscriberDocument()
    self.assertEqual(subscriber_document.getDescription(), self.description3)

  def test_15_ApplyPublisherValue(self, quiet=0, run=run_all_test):
    # We will try to generate a conflict and then to get it
    # We will also make sure it contains what we want
    if not run: return
    self.test_13_GetConflictList(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Apply Publisher Value ')
      LOG('Testing... ',0,'test_15_ApplyPublisherValue')
    portal_sync = self.getSynchronizationTool()
    conflict_list = portal_sync.getConflictList()
    conflict = conflict_list[0]
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    conflict.applyPublisherValue()
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    self.assertEqual(person1_c.getDescription(), self.description2)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    conflict_list = portal_sync.getConflictList()
    self.assertEqual(len(conflict_list), 0)

  def test_16_ApplySubscriberValue(self, quiet=0, run=run_all_test):
    # We will try to generate a conflict and then to get it
    # We will also make sure it contains what we want
    if not run: return
    self.test_13_GetConflictList(quiet=1,run=1)
    portal_sync = self.getSynchronizationTool()
    conflict_list = portal_sync.getConflictList()
    if not quiet:
      ZopeTestCase._print('\nTest Apply Subscriber Value ')
      LOG('Testing... ',0,'test_16_ApplySubscriberValue')
    conflict = conflict_list[0]
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    conflict.applySubscriberValue()
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    self.assertEqual(person1_s.getDescription(), self.description3)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    conflict_list = portal_sync.getConflictList()
    self.assertEqual(len(conflict_list), 0)

  def test_17_AddSubObject(self, quiet=0, run=run_all_test):
    """
    In this test, we synchronize, then add sub object on the
    server and then see if the next synchronization will also
    create sub-objects on the client
    """
    if not run: return
    self.test_08_FirstSynchronization(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Add Sub Object ')
      LOG('Testing... ',0,'test_17_AddSubObject')
    self.populatePersonServerWithSubObject(quiet=1,run=1)
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    self.checkSynchronizationStateIsSynchronized()
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    sub_person1_c = person1_c._getOb(self.id1)
    sub_sub_person1 = sub_person1_c._getOb(self.id1)
    sub_sub_person2 = sub_person1_c._getOb(self.id2)
    # remove ('','portal...','person_server')
    len_path = len(sub_sub_person1.getPhysicalPath()) - 3 
    self.assertEquals(len_path, 3)
    len_path = len(sub_sub_person2.getPhysicalPath()) - 3 
    self.assertEquals(len_path, 3)
    self.assertEquals(sub_sub_person1.getDescription(), self.description1)
    self.assertEquals(sub_sub_person1.getFirstName(), self.first_name1)
    self.assertEquals(sub_sub_person1.getLastName(), self.last_name1)
    self.assertEquals(sub_sub_person1.getDefaultTelephoneText(), '+(0)-0689778308')
    self.assertEquals(sub_sub_person2.getDescription(), self.description2)
    self.assertEquals(sub_sub_person2.getFirstName(), self.first_name2)
    self.assertEquals(sub_sub_person2.getLastName(), self.last_name2)
    #check two side (client, server)
    person_server = self.getPersonServer()
    sub_sub_person_s = person_server._getOb(self.id1)._getOb(self.id1)._getOb(self.id1)
    self.assertXMLViewIsEqual(self.sub_id1, sub_sub_person_s, sub_sub_person1)

  def test_18_UpdateSubObject(self, quiet=0, run=run_all_test):
    """
      In this test, we start with a tree of object already
    synchronized, then we update a subobject, and we will see
    if it is updated correctly.
      To make this test a bit more harder, we will update on both
    the client and the server by the same time
    """
    if not run: return
    self.test_17_AddSubObject(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Update Sub Object ')
      LOG('Testing... ',0,'test_18_UpdateSubObject')
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    sub_person1_c = person1_c._getOb(self.id1)
    sub_sub_person_c = sub_person1_c._getOb(self.id2)
    person_server = self.getPersonServer()
    sub_sub_person_s = person_server._getOb(self.id1)._getOb(self.id1)._getOb(self.id2)
    kw = {'first_name':self.first_name3}
    sub_sub_person_c.edit(**kw)
    kw = {'description':self.description3}
    sub_sub_person_s.edit(**kw)
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    self.assertEqual(sub_sub_person_c.getDescription(), self.description3)
    self.assertEqual(sub_sub_person_c.getFirstName(), self.first_name3)
    self.assertXMLViewIsEqual(self.sub_id1, sub_sub_person_s, sub_sub_person_c)

  def test_19_DeleteObject(self, quiet=0, run=run_all_test):
    """
      We will do a first synchronization, then delete an object on both
    sides, and we will see if nothing is left on the server and also
    on the two clients
    """
    if not run: return
    self.test_08_FirstSynchronization(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Delete Object ')
      LOG('Testing... ',0,'test_19_DeleteObject')
    person_server = self.getPersonServer()
    person_server.manage_delObjects(self.id1)
    person_client1 = self.getPersonClient1()
    person_client1.manage_delObjects(self.id2)
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    self.checkSynchronizationStateIsSynchronized()
    portal_sync = self.getSynchronizationTool()
    publication = portal_sync.getPublication(self.pub_id)
    subscription1 = portal_sync.getSubscription(self.sub_id1)
    subscription2 = portal_sync.getSubscription(self.sub_id2)
    self.assertEqual(len(publication.getObjectList()), 0)
    self.assertEqual(len(subscription1.getObjectList()), 0)
    self.assertEqual(len(subscription2.getObjectList()), 0)

  def test_20_DeleteSubObject(self, quiet=0, run=run_all_test):
    """
      We will do a first synchronization, then delete a sub-object on both
    sides, and we will see if nothing is left on the server and also
    on the two clients
    - before :         after :
      - id1             - id1 
        - id1             - id1
          - id2         - id2
          - id1
      - id2
    """
    if not run: return
    self.test_17_AddSubObject(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Delete Sub Object ')
      LOG('Testing... ',0,'test_20_DeleteSubObject')
    person_server = self.getPersonServer()
    sub_object_s = person_server._getOb(self.id1)._getOb(self.id1)
    sub_object_s.manage_delObjects(self.id1)
    person_client1 = self.getPersonClient1()
    sub_object_c1 = person_client1._getOb(self.id1)._getOb(self.id1)
    sub_object_c1.manage_delObjects(self.id2)
    person_client2 = self.getPersonClient2()
    sub_object_c2 = person_client2._getOb(self.id1)._getOb(self.id1)
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    self.checkSynchronizationStateIsSynchronized()
    len_s = len(sub_object_s.objectValues())
    len_c1 = len(sub_object_c1.objectValues())
    len_c2 = len(sub_object_c2.objectValues())
    self.failUnless(len_s==len_c1==len_c2==0)

  def test_21_GetConflictListOnSubObject(self, quiet=0, run=run_all_test):
    """
    We will change several attributes on a sub object on both the server
    and a client, then we will see if we have correctly the conflict list
    """
    if not run: return
    self.test_17_AddSubObject(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Get Conflict List On Sub Object ')
      LOG('Testing... ',0,'test_21_GetConflictListOnSubObject')
    person_server = self.getPersonServer()
    object_s = person_server._getOb(self.id1)
    sub_object_s = object_s._getOb(self.id1)
    person_client1 = self.getPersonClient1()
    sub_object_c1 = person_client1._getOb(self.id1)._getOb(self.id1)
    person_client2 = self.getPersonClient2()
    sub_object_c2 = person_client2._getOb(self.id1)._getOb(self.id1)
    # Change values so that we will get conflicts
    kw = {'language':self.lang2,'description':self.description2}
    sub_object_s.edit(**kw)
    kw = {'language':self.lang3,'description':self.description3}
    sub_object_c1.edit(**kw)
    self.synchronize(self.sub_id1)
    portal_sync = self.getSynchronizationTool()
    conflict_list = portal_sync.getConflictList()
    self.assertEqual(len(conflict_list), 2)
    conflict_list = portal_sync.getConflictList(sub_object_c1)
    self.assertEqual(len(conflict_list), 0)
    conflict_list = portal_sync.getConflictList(object_s)
    self.assertEqual(len(conflict_list), 0)
    conflict_list = portal_sync.getConflictList(sub_object_s)
    self.assertEqual(len(conflict_list), 2)

  def test_22_ApplyPublisherDocumentOnSubObject(self, quiet=0, run=run_all_test):
    """
    there's several conflict on a sub object, we will see if we can
    correctly have the publisher version of this document
    """
    if not run: return
    self.test_21_GetConflictListOnSubObject(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Apply Publisher Document On Sub Object ')
      LOG('Testing... ',0,'test_22_ApplyPublisherDocumentOnSubObject')
    portal_sync = self.getSynchronizationTool()
    conflict_list = portal_sync.getConflictList()
    conflict = conflict_list[0]
    conflict.applyPublisherDocument()
    person_server = self.getPersonServer()
    sub_object_s = person_server._getOb(self.id1)._getOb(self.id1)
    person_client1 = self.getPersonClient1()
    sub_object_c1 = person_client1._getOb(self.id1)._getOb(self.id1)
    person_client2 = self.getPersonClient2()
    sub_object_c2 = person_client2._getOb(self.id1)._getOb(self.id1)
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    self.checkSynchronizationStateIsSynchronized()
    self.assertEqual(sub_object_s.getDescription(), self.description2)
    self.assertEqual(sub_object_s.getLanguage(), self.lang2)
    self.assertXMLViewIsEqual(self.sub_id1, sub_object_s, sub_object_c1)
    self.assertXMLViewIsEqual(self.sub_id2, sub_object_s, sub_object_c2)

  def test_23_ApplySubscriberDocumentOnSubObject(self, quiet=0, run=run_all_test):
    """
    there's several conflict on a sub object, we will see if we can
    correctly have the subscriber version of this document
    """
    if not run: return
    self.test_21_GetConflictListOnSubObject(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Apply Subscriber Document On Sub Object ')
      LOG('Testing... ',0,'test_23_ApplySubscriberDocumentOnSubObject')
    portal_sync = self.getSynchronizationTool()
    conflict_list = portal_sync.getConflictList()
    conflict = conflict_list[0]
    conflict.applySubscriberDocument()
    person_server = self.getPersonServer()
    sub_object_s = person_server._getOb(self.id1)._getOb(self.id1)
    person_client1 = self.getPersonClient1()
    sub_object_c1 = person_client1._getOb(self.id1)._getOb(self.id1)
    person_client2 = self.getPersonClient2()
    sub_object_c2 = person_client2._getOb(self.id1)._getOb(self.id1)
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    self.checkSynchronizationStateIsSynchronized()
    self.assertEqual(sub_object_s.getDescription(), self.description3)
    self.assertEqual(sub_object_s.getLanguage(), self.lang3)
    self.assertXMLViewIsEqual(self.sub_id1, sub_object_s, sub_object_c1)
    self.assertXMLViewIsEqual(self.sub_id2, sub_object_s, sub_object_c2)

  def test_24_SynchronizeWithStrangeGid(self, quiet=0, run=run_all_test):
    """
    By default, the synchronization process use the id in order to
    recognize objects (because by default, getGid==getId. Here, we will see 
    if it also works with a somewhat strange getGid
    """
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Synchronize With Strange Gid ')
      LOG('Testing... ',0,'test_24_SynchronizeWithStrangeGid')
    self.login()
    self.setupPublicationAndSubscriptionAndGid(quiet=1,run=1)
    nb_person = self.populatePersonServer(quiet=1,run=1)
    # This will test adding object
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    portal_sync = self.getSynchronizationTool()
    subscription1 = portal_sync.getSubscription(self.sub_id1)
    self.assertEqual(len(subscription1.getObjectList()), nb_person)
    publication = portal_sync.getPublication(self.pub_id)
    self.assertEqual(len(publication.getObjectList()), nb_person)
    gid = self.first_name1 +  ' ' + self.last_name1 # ie the title 'Sebastien Robin'
    gid = b16encode(gid)
    person_c1 = subscription1.getObjectFromGid(gid)
    id_c1 = person_c1.getId()
    self.failUnless(id_c1 in ('1','2')) # id given by the default generateNewId
    person_s = publication.getSubscriber(self.subscription_url1).getObjectFromGid(gid)
    id_s = person_s.getId()
    self.assertEqual(id_s, self.id1)
    # This will test updating object
    person_s.setDescription(self.description3)
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    self.assertEqual(person_s.getDescription(), self.description3)
    self.assertEqual(person_c1.getDescription(), self.description3)
    self.assertXMLViewIsEqual(self.sub_id1, person_s, person_c1)
    # This will test deleting object
    person_server = self.getPersonServer()
    person_client1 = self.getPersonClient1()
    person_server.manage_delObjects(self.id2)
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    self.assertEqual(len(subscription1.getObjectList()), (nb_person-1))
    self.assertEqual(len(publication.getObjectList()), (nb_person-1))
    person_s = publication.getSubscriber(self.subscription_url1).getObjectFromGid(gid)
    person_c1 = subscription1.getObjectFromGid(gid)
    self.assertEqual(person_s.getDescription(), self.description3)
    self.assertXMLViewIsEqual(self.sub_id1, person_s, person_c1)

  def test_25_MultiNodeConflict(self, quiet=0, run=run_all_test):
    """
    We will create conflicts with 3 differents nodes, and we will
    solve it by taking one full version of documents.
    """
    if not run: return
    self.test_08_FirstSynchronization(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Multi Node Conflict ')
      LOG('Testing... ',0,'test_25_MultiNodeConflict')
    portal_sync = self.getSynchronizationTool()
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    kw = {'language':self.lang2,'description':self.description2,
          'format':self.format2}
    person1_s.edit(**kw)
    person_client1 = self.getPersonClient1()
    person1_c1 = person_client1._getOb(self.id1)
    kw = {'language':self.lang3,'description':self.description3,
          'format':self.format3}
    person1_c1.edit(**kw)
    person_client2 = self.getPersonClient2()
    person1_c2 = person_client2._getOb(self.id1)
    kw = {'language':self.lang4,'description':self.description4,
          'format':self.format4}
    person1_c2.edit(**kw)
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    conflict_list = portal_sync.getConflictList()
    self.assertEqual(len(conflict_list), 6)
    # check if we have the state conflict on all clients
    self.checkSynchronizationStateIsConflict()
    # we will take :
    # description on person_server
    # language on person_client1
    # format on person_client2
    
    for conflict in conflict_list : 
      subscriber = conflict.getSubscriber()
      property = conflict.getPropertyId()
      resolve = 0
      if property == 'language':
        if subscriber.getSubscriptionUrl()==self.subscription_url1:
          resolve = 1
          conflict.applySubscriberValue()
      if property == 'format':
        if subscriber.getSubscriptionUrl()==self.subscription_url2:
          resolve = 1
          conflict.applySubscriberValue()
      if not resolve:
        conflict.applyPublisherValue()
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    self.checkSynchronizationStateIsSynchronized()
    self.assertEqual(person1_c1.getDescription(), self.description2)
    self.assertEqual(person1_c1.getLanguage(), self.lang3)
    self.assertEqual(person1_c1.getFormat(), self.format4)
    self.assertEqual(person1_s.getDescription(), self.description2)
    self.assertEqual(person1_s.getLanguage(), self.lang3)
    self.assertEqual(person1_s.getFormat(), self.format4)
    self.assertXMLViewIsEqual(self.sub_id2, person1_s, person1_c2)
    # the workflow has one more "edit_workflow" in person1_c1 
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    self.assertXMLViewIsEqual(self.sub_id2, person1_s, person1_c2)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c1)

  def test_26_SynchronizeWorkflowHistory(self, quiet=0, run=run_all_test):
    """
    We will do a synchronization, then we will edit two times
    the object on the server, then two times the object on the
    client, and see if the global history as 4 more actions.
    """
    if not run: return
    self.test_08_FirstSynchronization(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Synchronize WorkflowHistory ')
      LOG('Testing... ',0,'test_26_SynchronizeWorkflowHistory')
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    kw1 = {'description':self.description1}
    kw2 = {'description':self.description2}
    len_wf = len(person1_s.workflow_history[self.workflow_id])
    person1_s.edit(**kw2)
    person1_c.edit(**kw2)
    person1_s.edit(**kw1)
    person1_c.edit(**kw1)
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    self.assertEqual(len(person1_s.workflow_history[self.workflow_id]), len_wf+4)
    self.assertEqual(len(person1_c.workflow_history[self.workflow_id]), len_wf+4)

  def test_27_UpdateLocalRole(self, quiet=0, run=run_all_test):
    """
    We will do a first synchronization, then modify, add and delete
    an user role and see if it is correctly synchronized
    """
    if not run: return
    self.test_08_FirstSynchronization(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Update Local Role ')
      LOG('Testing... ',0,'test_27_UpdateLocalRole')
    # First, Create a new user
    uf = self.getPortal().acl_users
    uf._doAddUser('jp', '', ['Manager'], [])
    user = uf.getUserById('jp').__of__(uf)
    # then update create and delete roles
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    person2_s = person_server._getOb(self.id2)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    person2_c = person_client1._getOb(self.id2)
    person1_s.manage_setLocalRoles('fab',['Manager','Owner'])
    person2_s.manage_setLocalRoles('jp',['Manager','Owner'])
    person2_s.manage_delLocalRoles(['fab'])
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    self.assertXMLViewIsEqual(self.sub_id2, person2_s, person2_c)
    role_1_s = person1_s.get_local_roles()
    role_2_s = person2_s.get_local_roles()
    role_1_c = person1_c.get_local_roles()
    role_2_c = person2_c.get_local_roles()
    self.assertEqual(role_1_s,role_1_c)
    self.assertEqual(role_2_s,role_2_c)

  def test_28_PartialData(self, quiet=0, run=run_all_test):
    """
    We will do a first synchronization, then we will do a change, then
    we will modify the SyncCode max_line value so it
    it will generate many messages
    """
    if not run: return
    self.test_08_FirstSynchronization(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Partial Data ')
      LOG('Testing... ',0,'test_28_PartialData')
    previous_max_lines = SyncCode.MAX_LINES
    SyncCode.MAX_LINES = 10
    self.populatePersonServerWithSubObject(quiet=1,run=1)
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    self.checkSynchronizationStateIsSynchronized()
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    sub_person1_c = person1_c._getOb(self.id1)
    sub_sub_person1 = sub_person1_c._getOb(self.id1)
    sub_sub_person2 = sub_person1_c._getOb(self.id2)
    # remove ('','portal...','person_server')
    len_path = len(sub_sub_person1.getPhysicalPath()) - 3 
    self.assertEqual(len_path, 3)
    len_path = len(sub_sub_person2.getPhysicalPath()) - 3 
    self.assertEqual(len_path, 3)
    self.assertEquals(sub_sub_person1.getDescription(),self.description1)
    self.assertEquals(sub_sub_person1.getFirstName(),self.first_name1)
    self.assertEquals(sub_sub_person1.getLastName(),self.last_name1)
    self.assertEquals(sub_sub_person2.getDescription(),self.description2)
    self.assertEquals(sub_sub_person2.getFirstName(),self.first_name2)
    self.assertEquals(sub_sub_person2.getLastName(),self.last_name2)
    SyncCode.MAX_LINES = previous_max_lines

  def test_29_BrokenMessage(self, quiet=0, run=run_all_test):
    """
    With http synchronization, when a message is not well
    received, then we send message again, we want to
    be sure that is such case we don't do stupid things
    
    If we want to make this test more intersting, it is
    better to split messages
    """
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Broken Message ')
      LOG('Testing... ',0,'test_29_BrokenMessage')
    previous_max_lines = SyncCode.MAX_LINES
    SyncCode.MAX_LINES = 10
    self.setupPublicationAndSubscription(quiet=1,run=1)
    nb_person = self.populatePersonServer(quiet=1,run=1)
    # Synchronize the first client
    nb_message1 = self.synchronizeWithBrokenMessage(self.sub_id1)
    #self.failUnless(nb_message1==self.nb_message_first_synchronization)
    portal_sync = self.getSynchronizationTool()
    subscription1 = portal_sync.getSubscription(self.sub_id1)
    self.assertEqual(len(subscription1.getObjectList()), nb_person)
    person_server = self.getPersonServer() # We also check we don't
                                           # modify initial ob
    person1_s = person_server._getOb(self.id1)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    self.assertEqual(person1_s.getId(), self.id1)
    self.assertEqual(person1_s.getFirstName(), self.first_name1)
    self.assertEqual(person1_s.getLastName(), self.last_name1)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    SyncCode.MAX_LINES = previous_max_lines

  def test_30_GetSynchronizationType(self, quiet=0, run=run_all_test):
    # We will try to update some simple data, first
    # we change on the server side, then on the client side
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Get Synchronization Type ')
      LOG('Testing... ',0,'test_30_GetSynchronizationType')
    self.test_08_FirstSynchronization(quiet=1,run=1)
    # First we do only modification on server
    # Check for each subsription that the synchronization type
    # is TWO WAY
    portal_sync = self.getSynchronizationTool()
    for sub in portal_sync.getSubscriptionList():
      self.assertEquals(sub.getSynchronizationType(),SyncCode.TWO_WAY)
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    kw = {'first_name':self.first_name3,'last_name':self.last_name3}
    person1_s.edit(**kw)
    self.synchronize(self.sub_id1)
    # Then we do only modification on a client
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    kw = {'first_name':self.first_name1,'last_name':self.last_name1}
    person1_c.edit(**kw)
    self.synchronize(self.sub_id1)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    for sub in portal_sync.getSubscriptionList():
      self.assertEquals(sub.getSynchronizationType(),SyncCode.TWO_WAY)
    # Then we do only modification on both the client and the server
    # and of course, on the same object
    kw = {'first_name':self.first_name3}
    person1_s.edit(**kw)
    kw = {'description':self.description3}
    person1_c.edit(**kw)
    self.synchronize(self.sub_id1)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    for sub in portal_sync.getSubscriptionList():
      self.assertEquals(sub.getSynchronizationType(),SyncCode.TWO_WAY)

  def test_31_UpdateLocalPermission(self, quiet=0, run=run_all_test):
    """
    We will do a first synchronization, then modify, add and delete
    an user role and see if it is correctly synchronized
    """
    if not run: return
    self.test_08_FirstSynchronization(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Update Local Permission ')
      LOG('Testing... ',0,'test_31_UpdateLocalPermission')
    # then create roles
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    person2_s = person_server._getOb(self.id2)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    person2_c = person_client1._getOb(self.id2)
    person1_s.manage_setLocalPermissions('View',['Manager','Owner'])
    person2_s.manage_setLocalPermissions('View',['Manager','Owner'])
    person2_s.manage_setLocalPermissions('View management screens',['Owner',])
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    role_1_s = person1_s.get_local_permissions()
    role_2_s = person2_s.get_local_permissions()
    role_1_c = person1_c.get_local_permissions()
    role_2_c = person2_c.get_local_permissions()
    self.assertEqual(role_1_s,role_1_c)
    self.assertEqual(role_2_s,role_2_c)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    self.assertXMLViewIsEqual(self.sub_id2, person2_s, person2_c)
    person1_s.manage_setLocalPermissions('View',['Owner'])
    person2_s.manage_setLocalPermissions('View',None)
    person2_s.manage_setLocalPermissions('View management screens',())
    self.synchronize(self.sub_id1)
    self.synchronize(self.sub_id2)
    role_1_s = person1_s.get_local_permissions()
    role_2_s = person2_s.get_local_permissions()
    role_1_c = person1_c.get_local_permissions()
    role_2_c = person2_c.get_local_permissions()
    self.assertEqual(role_1_s,role_1_c)
    self.assertEqual(role_2_s,role_2_c)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    self.assertXMLViewIsEqual(self.sub_id2, person2_s, person2_c)

  def test_32_AddOneWaySubscription(self, quiet=0, run=run_all_test):
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Add One Way Subscription ')
      LOG('Testing... ',0,'test_32_AddOneWaySubscription')
    portal_id = self.getPortalId()
    portal_sync = self.getSynchronizationTool()
    if portal_sync.getSubscription(self.sub_id1) is not None:
      portal_sync.manage_deleteSubscription(title=self.sub_id1)
    portal_sync.manage_addSubscription(title=self.sub_id1,
        publication_url=self.publication_url,
        subscription_url=self.subscription_url1,
        destination_path='/%s/person_client1' % portal_id,
        source_uri='Person',
        target_uri='Person',
        query='objectValues',
        xml_mapping=self.xml_mapping,
        conduit='ERP5Conduit',
        gpg_key='',
        activity_enabled=self.activity_enabled,
        alert_code = SyncCode.ONE_WAY_FROM_SERVER,
        login = 'fab',
        password = 'myPassword')
    sub = portal_sync.getSubscription(self.sub_id1)
    self.assertTrue(sub.isOneWayFromServer())
    self.failUnless(sub is not None)

  def test_33_OneWaySync(self, quiet=0, run=run_all_test):
    """
    We will test if we can synchronize only from to server to the client.
    We want to make sure in this case that all modifications on the client
    will not be taken into account.
    """
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest One Way Sync ')
      LOG('Testing... ',0,'test_33_OneWaySync')
    person_server = self.getPersonServer()
    if person_server is not None:
      portal = self.getPortal()
      portal._delObject(id='person_server')
      portal._delObject(id='person_client1')
      portal._delObject(id='person_client2')
      self.deletePublicationAndSubscription() 
    self.test_02_AddPublication(quiet=1,run=1)
    self.test_32_AddOneWaySubscription(quiet=1,run=1)

    nb_person = self.populatePersonServer(quiet=1,run=1)
    portal_sync = self.getSynchronizationTool()
    for sub in portal_sync.getSubscriptionList():
      self.assertEquals(sub.getSynchronizationType(), SyncCode.SLOW_SYNC)
    # First do the sync from the server to the client
    nb_message1 = self.synchronize(self.sub_id1)
    for sub in portal_sync.getSubscriptionList():
      self.assertEquals(sub.getSynchronizationType(), SyncCode.ONE_WAY_FROM_SERVER)
    self.assertEquals(nb_message1,self.nb_message_first_synchronization)
    subscription1 = portal_sync.getSubscription(self.sub_id1)
    self.assertEquals(len(subscription1.getObjectList()),nb_person)
    person_server = self.getPersonServer() # We also check we don't
                                           # modify initial ob
    person1_s = person_server._getOb(self.id1)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)
    self.assertEqual(person1_s.getId(), self.id1)
    self.assertEqual(person1_s.getFirstName(), self.first_name1)
    self.assertEqual(person1_s.getLastName(), self.last_name1)
    self.checkSynchronizationStateIsSynchronized()
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c, force=1)
    # Then we change things on both sides and we look if there
    # is synchronization from only one way
    person1_c.setFirstName(self.first_name2)
    person1_s.setLastName(self.last_name2)
    nb_message1 = self.synchronize(self.sub_id1)
    #In One_From_Server Sync not modify the first_name in client because any
    #datas client sent
    self.assertEquals(person1_c.getFirstName(), self.first_name2)
    self.assertEquals(person1_c.getLastName(), self.last_name2)
    self.assertEquals(person1_s.getFirstName(), self.first_name1)
    self.assertEquals(person1_s.getLastName(), self.last_name2) 
    #reset for refresh sync
    #after synchronize, the client object retrieve value of server
    self.resetSignaturePublicationAndSubscription()
    nb_message1 = self.synchronize(self.sub_id1)
    self.assertEquals(person1_s.getFirstName(), self.first_name1)
    self.assertEquals(person1_s.getLastName(), self.last_name2) 
    self.checkSynchronizationStateIsSynchronized()
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c, force=1)

  def test_34_encoding(self, quiet=0, run=run_all_test):
    """
    We will test if we can encode strings with b64encode to encode
    the login and password for authenticated sessions
    """
    #when there will be other format implemented with encode method,
    #there will be tested here

    if not run: return
    self.test_08_FirstSynchronization(quiet=1,run=1)
    if not quiet:
      ZopeTestCase._print('\nTest Strings Encoding ')
      LOG('Testing... ',0,'test_34_encoding')
      
    #define some strings :
    python = 'www.python.org'
    awaited_result_python = "d3d3LnB5dGhvbi5vcmc="
    long_string = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNO\
PQRSTUVWXYZéèçà@^~µ&²0123456789!@#0^&*();:<>,. []{}\xc3\xa7sdf__\
sdf\xc3\xa7\xc3\xa7\xc3\xa7_df___&&\xc3\xa9]]]\xc2\xb0\xc2\xb0\xc2\
\xb0\xc2\xb0\xc2\xb0\xc2\xb0"
    #= "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZéèçà@^~µ&²012345
    #6789!@#0^&*();:<>,. []{}çsdf__sdfççç_df___&&é]]]°°°°°°'"

    awaited_result_long_string = "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXpBQkNERUZH\
SElKS0xNTk9QUVJTVFVWV1hZWsOpw6jDp8OgQF5+wrUmwrIwMTIzNDU2Nzg5IUAjMF4mKigpOzo8Pi\
wuIFtde33Dp3NkZl9fc2Rmw6fDp8OnX2RmX19fJibDqV1dXcKwwrDCsMKwwrDCsA=="
    #test just b64encode
    self.assertEqual(b64encode(python), awaited_result_python)
    self.assertEqual(b64encode(""), "")
    self.assertEqual(b64encode(long_string), awaited_result_long_string)
    
    self.assertEqual(b64decode(awaited_result_python), python)
    self.assertEqual(b64decode(""), "")
    self.assertEqual(b64decode(awaited_result_long_string), long_string)

    # test with the ERP5 functions
    portal_sync = self.getSynchronizationTool()
    publication = portal_sync.getPublication(self.pub_id)
    subscription1 = portal_sync.getSubscription(self.sub_id1)
      
    string_encoded = subscription1.encode('b64', python)
    self.assertEqual(string_encoded, awaited_result_python)
    string_decoded = subscription1.decode('b64', awaited_result_python)
    self.assertEqual(string_decoded, python)
    self.failUnless(subscription1.isDecodeEncodeTheSame(string_encoded, 
      python, 'b64'))
    self.failUnless(subscription1.isDecodeEncodeTheSame(string_encoded, 
      string_decoded, 'b64'))

    string_encoded = subscription1.encode('b64', long_string) 
    self.assertEqual(string_encoded, awaited_result_long_string)
    string_decoded = subscription1.decode('b64', awaited_result_long_string)
    self.assertEqual(string_decoded, long_string)
    self.failUnless(subscription1.isDecodeEncodeTheSame(string_encoded, 
      long_string, 'b64'))
    self.failUnless(subscription1.isDecodeEncodeTheSame(string_encoded, 
      string_decoded, 'b64'))

    self.assertEqual(subscription1.encode('b64', ''), '')
    self.assertEqual(subscription1.decode('b64', ''), '')
    self.failUnless(subscription1.isDecodeEncodeTheSame(
      subscription1.encode('b64', ''), '', 'b64'))

  def test_35_authentication(self, quiet=0, run=run_all_test):
    """
      we will test 
      - if we can't synchronize without good authentication for an 
      autentication required publication.
      - if we can synchronize without of with (and bad or good) authentication
      for an not required autentication publication
    """

    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Authentication ')
      LOG('Testing... ',0,'test_35_authentication')
    
    self.test_08_FirstSynchronization(quiet=1,run=1)
    # First we do only modification on client
    portal_sync = self.getSynchronizationTool()
    person_server = self.getPersonServer()
    person1_s = person_server._getOb(self.id1)
    person_client1 = self.getPersonClient1()
    person1_c = person_client1._getOb(self.id1)

    kw = {'first_name':self.first_name3,'last_name':self.last_name3}
    person1_c.edit(**kw)
   
    #check that it's not synchronize
    self.verifyFirstNameAndLastNameAreNotSynchronized(self.first_name3,
      self.last_name3, person1_s, person1_c)
    self.synchronize(self.sub_id1)
    #now it should be synchronize
    self.checkSynchronizationStateIsSynchronized()
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    self.assertEquals(person1_s.getFirstName(), self.first_name3)
    self.assertEquals(person1_s.getLastName(), self.last_name3)
 
    #adding authentication :
    self.addAuthenticationToPublication(self.pub_id, 'fab', 'myPassword', 'b64',
        'syncml:auth-basic')
    self.addAuthenticationToSubscription(self.sub_id1, 'pouet', 'pouet', 
        'b64', 'syncml:auth-basic')
    # try to synchronize with a wrong authentication on the subscription, it 
    # should failed
    kw = {'first_name':self.first_name2,'last_name':self.last_name2}
    person1_c.edit(**kw)
    self.verifyFirstNameAndLastNameAreNotSynchronized(self.first_name2, 
      self.last_name2, person1_s, person1_c)
    # here, before and after synchronization, the person1_s shoudn't have
    # the name as the person1_c because the user isn't authenticated
    self.synchronize(self.sub_id1)
    self.verifyFirstNameAndLastNameAreNotSynchronized(self.first_name2, 
      self.last_name2, person1_s, person1_c)

    #try to synchronize whith an authentication on both the client and server
    self.addAuthenticationToSubscription(self.sub_id1, 'fab', 'myPassword', 
        'b64', 'syncml:auth-basic')
    #now it should be correctly synchronize
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    self.assertEquals(person1_s.getFirstName(), self.first_name2)
    self.assertEquals(person1_s.getLastName(), self.last_name2)

    #try to synchronize with a bad login and/or password
    #test if login is case sensitive (it should be !)
    self.addAuthenticationToSubscription(self.sub_id1, 'fAb', 'myPassword', 
        'b64', 'syncml:auth-basic')
    kw = {'first_name':self.first_name1,'last_name':self.last_name1}
    person1_c.edit(**kw)
    self.synchronize(self.sub_id1)
    self.verifyFirstNameAndLastNameAreNotSynchronized(self.first_name1, 
      self.last_name1, person1_s, person1_c)

    #with a paswword case sensitive
    self.addAuthenticationToSubscription(self.sub_id1, 'fab', 'mypassword', 
        'b64', 'syncml:auth-basic')
    kw = {'first_name':self.first_name1,'last_name':self.last_name1}
    person1_c.edit(**kw)
    self.synchronize(self.sub_id1)
    self.verifyFirstNameAndLastNameAreNotSynchronized(self.first_name1, 
      self.last_name1, person1_s, person1_c)
    
    #with the good password
    self.addAuthenticationToSubscription(self.sub_id1, 'fab', 'myPassword', 
        'b64', 'syncml:auth-basic')
    #now it should be correctly synchronize
    self.synchronize(self.sub_id1)
    self.checkSynchronizationStateIsSynchronized()
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    self.assertEquals(person1_s.getFirstName(), self.first_name1)
    self.assertEquals(person1_s.getLastName(), self.last_name1)

    #verify that the login and password with utf8 caracters are accecpted

    # add a user with an utf8 login
    uf = self.getPortal().acl_users
    uf._doAddUser('\xc3\xa9pouet', 'ploum', ['Manager'], []) # \xc3\xa9pouet = épouet
    user = uf.getUserById('\xc3\xa9pouet').__of__(uf)
    newSecurityManager(None, user)

    self.addAuthenticationToPublication(self.pub_id, '\xc3\xa9pouet', 'ploum', 
        'b64', 'syncml:auth-basic')
    #first, try with a wrong login :
    self.addAuthenticationToSubscription(self.sub_id1, 'pouet', 'ploum', 
        'b64', 'syncml:auth-basic')
    kw = {'first_name':self.first_name3,'last_name':self.last_name3}
    person1_c.edit(**kw)
    self.verifyFirstNameAndLastNameAreNotSynchronized(self.first_name3, 
      self.last_name3, person1_s, person1_c)
    self.synchronize(self.sub_id1)
    self.verifyFirstNameAndLastNameAreNotSynchronized(self.first_name3, 
      self.last_name3, person1_s, person1_c)
    #now with the good :
    self.addAuthenticationToSubscription(self.sub_id1, '\xc3\xa9pouet', 'ploum',
        'b64', 'syncml:auth-basic')
    self.synchronize(self.sub_id1)
    self.assertXMLViewIsEqual(self.sub_id1, person1_s, person1_c)
    self.assertEquals(person1_s.getFirstName(), self.first_name3)
    self.assertEquals(person1_s.getLastName(), self.last_name3)
    self.checkSynchronizationStateIsSynchronized()

  def test_36_SynchronizationSubscriptionMaxLines(self, quiet=0, run=run_all_test):
    # We will try to populate the folder person_server
    # with the data form person_client 
    # with the data which over max line of messages
    if not run: return
    if not quiet:
      ZopeTestCase._print('\nTest Synchronization Subscription Max Lines')
      LOG('Testing... ',0,'test_36_SynchronizationSubscriptionMaxLines')
    self.login()
    self.setupPublicationAndSubscription(quiet=1, run=1)
    nb_person = self.populatePersonClient1(quiet=1, run=1)
    portal_sync = self.getSynchronizationTool()
    for sub in portal_sync.getSubscriptionList():
      self.assertEquals(sub.getSynchronizationType(), SyncCode.SLOW_SYNC)
    # Synchronize the first client
    # data_Sub1 -> Pub (the data are in sub1 to pub is empty)
    nb_message1 = self.synchronize(self.sub_id1)
    #Verification number object synchronized
    self.assertEqual(nb_message1, self.nb_message_first_sync_max_lines)
    # Synchronize the second client
    # data_Pub -> data_Sub2 the data are in pub to sub2 is empty so add +2 messages)
    nb_message2 = self.synchronize(self.sub_id2)
    self.assertEqual(nb_message2, self.nb_message_first_sync_max_lines + 2)
    person_server = self.getPersonServer()
    person_client1 = self.getPersonClient1()
    person_client2 = self.getPersonClient2()
    for id in range(1, 60):
      person_s = person_server._getOb(str(id))
      person_c = person_client1._getOb(str(id))
      self.assertXMLViewIsEqual(self.sub_id1, person_s, person_c)
    self.assertEqual(nb_person, len(person_server.objectValues()))
    self.assertEqual(nb_person, len(person_client2.objectValues()))

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestERP5SyncML))
    return suite

