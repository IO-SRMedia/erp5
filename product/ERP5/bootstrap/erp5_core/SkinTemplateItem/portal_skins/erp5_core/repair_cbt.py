"""
for ptype in context.getPortalObject().portal_types.objectValues():
  for workflow_id in ['interactionworkflow_testing_interaction_workflow', 'workflow_testing_workflow']:
    ptype.delTypeWorkflowList(workflow_id)

"""
# rapair _chains_by_type
type_workflow_dict = {'Category': ('edit_workflow',), 'Dynamic Category Property': ('dynamic_class_generation_interaction_workflow',), 'System Preference': ('edit_workflow', 'preference_workflow'), 'Bug Line': ('edit_workflow', 'bug_event_workflow'), 'Embedded Folder': ('edit_workflow', 'embedded_workflow'), 'Test Component': ('edit_workflow', 'dynamic_class_generation_interaction_workflow', 'component_validation_workflow'), 'Base Category': ('edit_workflow', 'dynamic_class_generation_interaction_workflow'), 'Organisation': ('validation_workflow', 'edit_workflow'), 'Property Type Validity Constraint': ('dynamic_class_generation_interaction_workflow',), 'Property Existence Constraint': ('dynamic_class_generation_interaction_workflow',), 'Action Information': ('base_type_interaction_workflow',), 'ERP5Workflow Test Document': ('testing_workflow', 'testing_interaction_workflow', 'edit_workflow'), 'Document': ('edit_workflow',), 'Email': ('edit_workflow',), 'Career': ('career_workflow',), 'Document Component': ('edit_workflow', 'dynamic_class_generation_interaction_workflow', 'component_validation_workflow'), 'Category Acquired Membership State Constraint': ('dynamic_class_generation_interaction_workflow',), 'Predicate': ('rule_interaction_workflow', 'edit_workflow'), 'Category Tool': ('dynamic_class_generation_interaction_workflow',), 'Attribute Unicity Constraint': ('dynamic_class_generation_interaction_workflow',), 'Role Definition': ('edit_workflow', 'local_permission_interaction_workflow'), 'Category Membership State Constraint': ('dynamic_class_generation_interaction_workflow',), 'Assignment': ('edit_workflow', 'assignment_workflow'), 'Distributed Ram Cache': ('distributed_ram_cache_interaction_workflow',), 'Rounding Model': ('validation_workflow',), 'Component': ('validation_workflow', 'edit_workflow'), 'Configuration Save': ('edit_workflow',), 'Link': ('edit_workflow',), 'Preference': ('edit_workflow', 'preference_workflow'), 'Address': ('edit_workflow',), 'TALES Constraint': ('dynamic_class_generation_interaction_workflow',), 'Category Property': ('dynamic_class_generation_interaction_workflow',), 'Category Related Membership Arity Constraint': ('dynamic_class_generation_interaction_workflow',), 'Content Existence Constraint': ('dynamic_class_generation_interaction_workflow',), 'Notification Message': ('document_security_interaction_workflow', 'notification_message_workflow', 'processing_status_workflow', 'document_conversion_interaction_workflow', 'edit_workflow'), 'Acquired Property': ('dynamic_class_generation_interaction_workflow',), 'Property Sheet': ('dynamic_class_generation_interaction_workflow',), 'Embedded File': ('edit_workflow', 'embedded_workflow', 'document_conversion_interaction_workflow'), 'Category Membership Arity Constraint': ('dynamic_class_generation_interaction_workflow',), 'Category Related Membership State Constraint': ('dynamic_class_generation_interaction_workflow',), 'Alarm': ('edit_workflow',), 'Bank Account': ('validation_workflow', 'edit_workflow'), 'Fax': ('edit_workflow',), 'Mapped Value': ('edit_workflow',), 'Business Template': ('business_template_building_workflow', 'business_template_installation_workflow'), 'Memcached Plugin': ('memcached_plugin_interaction_workflow',), 'Attribute Blacklisted Constraint': ('dynamic_class_generation_interaction_workflow',), 'Category Existence Constraint': ('dynamic_class_generation_interaction_workflow',), 'Query': ('edit_workflow', 'query_workflow'), 'Attribute Equality Constraint': ('dynamic_class_generation_interaction_workflow',), 'Simulation Movement': ('simulation_movement_causality_interaction_workflow',), 'Person': ('validation_workflow', 'edit_workflow', 'person_interaction_workflow', 'user_account_workflow'), 'File': ('document_security_interaction_workflow', 'document_conversion_interaction_workflow', 'edit_workflow'), 'ERP5Workflow Test Object': ('dc_test_workflow',), 'Glossary Term': ('validation_workflow', 'edit_workflow'), 'Telephone': ('edit_workflow',), 'Agent': ('edit_workflow',), 'Bug': ('edit_workflow', 'bug_workflow'), 'String Attribute Match Constraint': ('dynamic_class_generation_interaction_workflow',), 'Currency': ('validation_workflow', 'edit_workflow'), 'Base Type': ('dynamic_class_generation_interaction_workflow', 'base_type_interaction_workflow'), 'Extension Component': ('edit_workflow', 'dynamic_class_generation_interaction_workflow', 'component_validation_workflow'), 'Chat Address': ('edit_workflow',), 'Credit Card': ('validation_workflow', 'edit_workflow'), 'Currency Exchange Line': ('currency_exchange_line_interaction_workflow', 'edit_workflow', 'validation_workflow'), 'Business Configuration': ('validation_workflow', 'edit_workflow', 'business_configuration_simulation_workflow'), 'Standard Property': ('dynamic_class_generation_interaction_workflow',), 'Image': ('document_security_interaction_workflow', 'document_conversion_interaction_workflow', 'edit_workflow'), 'Property Sheet Tool': ('dynamic_class_generation_interaction_workflow',)}
chains_by_type = context.getChainsByType()

# the workflow_id to repair
workflow_id_to_repair_list = ['edit_workflow', 'validation_workflow']

# repair process
for workflow_id in workflow_id_to_repair_list:
  for type_id in chains_by_type:
    type_ob = getattr(context.getPortalObject().portal_types, type_id, None)
    if type_ob is not None:
      if workflow_id in type_workflow_dict[type_id] and workflow_id not in chains_by_type[type_id]:
        #raise NotImplementedError(type_id, type_workflow_dict[type_id], chains_by_type[type_id])
        context.addTypeCBT(type_id, workflow_id)
        if type_ob is not None:
          type_ob.delTypeWorkflowList('workflow_'+workflow_id)
          type_ob.delTypeWorkflowList('interactionworkflow_'+workflow_id)
