##parameters=selection_name='',form_id='',uids=[],listbox_uid=[]

request = context.REQUEST

list_actions = context.portal_actions.listFilteredActionsFor(context)
print_actions = list_actions['object_print']
url = print_actions[0]['url']

context.portal_selections.updateSelectionCheckedUidList(selection_name,listbox_uid,uids)
url += '?selection_name=%s&dialog_category=%s&form_id=%s' % (selection_name , 'object_print', form_id) 
request.RESPONSE.redirect(url)
