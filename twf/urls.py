"""Urls for the twf app."""
from django.urls import path
from django.contrib.auth import views as auth_views

from twf.tasks.task_status import task_status_view
from twf.tasks.task_triggers import *
from twf.views.ajax.views_ajax_field_validation import validate_page_field, validate_document_field
from twf.views.ajax.views_ajax_markdown import ajax_markdown_generate, ajax_markdown_preview
from twf.views.ajax.views_ajax_notes import save_ai_result_as_note
from twf.views.ajax.views_ajax_prompts import load_prompt, save_prompt, get_prompts
from twf.views.ajax.views_ajax_transkribus_export import ajax_transkribus_request_export, \
    ajax_transkribus_reset_export, ajax_transkribus_request_export_status
from twf.views.collections.views_collections_ai import \
    TWFUnifiedCollectionAIBatchView, TWFUnifiedCollectionAIRequestView
from twf.views.collections.views_crud import delete_collection, set_col_item_status_open, set_col_item_status_reviewed, \
    set_col_item_status_faulty, split_collection_item, copy_collection_item, delete_collection_item_annotation, \
    delete_collection_item, download_collection_item_txt, download_collection_item_json, \
    update_collection_item_metadata, delete_collection_item_metadata
from twf.views.dictionaries.views_dictionaries_ai import TWFDictionaryGNDBatchView, TWFDictionaryGeonamesBatchView, \
    TWFDictionaryWikidataBatchView, TWFDictionaryGNDRequestView, TWFDictionaryGeonamesRequestView, \
    TWFDictionaryWikidataRequestView, \
    TWFUnifiedDictionaryAIBatchView, TWFUnifiedDictionaryAIRequestView
from twf.views.dictionaries.views_crud import remove_dictionary_from_project, add_dictionary_to_project, skip_entry, \
    delete_variation, delete_dictionary_entry, update_dictionary_entry_metadata, delete_dictionary_entry_metadata, \
    save_entry_metadata_json, search_entry_geonames, search_entry_gnd, search_entry_wikidata, save_entry_lookup
from twf.views.documents.views_crud import update_document_metadata, delete_document_metadata
from twf.views.documents.views_documents import TWFDocumentsOverviewView, TWFDocumentsBrowseView, \
    TWFDocumentNameView, TWFDocumentDetailView, TWFDocumentReviewView, TWFDocumentsSearchView
from twf.views.documents.views_documents_ai import TWFUnifiedDocumentBatchView
from twf.views.export.views_crud import delete_export, delete_export_configuration, disconnect_zenodo, connect_zenodo, \
    create_zenodo_connection
from twf.views.home.views_home import TWFHomeView, TWFHomeLoginView, TWFHomePasswordChangeView, TWFHomeUserOverView, \
    TWFSelectProjectView, TWFHomeUserProfileView, TWFCreateProjectView, TWFManageProjectsView, TWFManageUsersView, \
    TWFSystemHealthView, check_system_health, TWFHomeIndexView, TWFHomeAboutView, TWFProjectViewDetailView, \
    TWFUserDetailView, TWFProjectListView
from twf.views.home.views_crud import activate_user, deactivate_user, delete_user, reset_password
from twf.views.metadata.views_metadata_ai import TWFMetadataLoadDataView, TWFMetadataLoadSheetsDataView
from twf.views.project.views_crud import delete_all_documents, delete_all_tags, delete_all_collections, select_project, \
    delete_project, close_project, reopen_project, delete_prompt, task_cancel_view, task_remove_view, delete_note, \
    unpark_all_tags, remove_all_prompts, remove_all_tasks, remove_all_dictionaries, update_user_permissions
from twf.views.ajax.views_ajax_download import ajax_transkribus_download_export, download_progress_view
from twf.views.collections.views_collections import TWFCollectionsReviewView, TWFCollectionOverviewView, \
    TWFCollectionsCreateView, TWFCollectionsDetailView, TWFCollectionsEditView, TWFCollectionsAddDocumentView, \
    TWFCollectionItemEditView, TWFCollectionItemView, TWFCollectionListView
from twf.views.views_base import help_content
from twf.views.tags.views_crud import park_tag, park_all_identical_tags, unpark_tag, ungroup_tag, delete_tag
from twf.views.dictionaries.views_dictionaries import TWFDictionaryOverviewView, TWFDictionaryDictionaryView, \
    TWFDictionaryDictionaryEditView, TWFDictionaryDictionaryEntryEditView, TWFDictionaryDictionaryEntryView, \
    TWFDictionaryNormDataView, TWFDictionaryCreateView, TWFDictionaryDictionariesView, \
    TWFDictionaryAddView, TWFDictionaryMergeEntriesView
from twf.views.export.views_export import TWFExportProjectView, \
    TWFExportOverviewView, TWFImportDictionaryView, \
    TWFExportConfigurationView, TWFExportZenodoView, TWFExportListView, TWFExportConfListView, TWFExportRunView, \
    TWFExportSampleView, TWFExportZenodoVersionView
from twf.views.metadata.views_metadata import TWFMetadataReviewDocumentsView, TWFMetadataExtractTagsView, \
    TWFMetadataReviewPagesView, TWFMetadataOverviewView
from twf.views.project.views_project import TWFProjectQueryView, TWFProjectOverviewView, \
    TWFProjectTaskMonitorView, TWFProjectTaskDetailView, TWFProjectGeneralSettingsView, \
    TWFProjectCredentialsSettingsView, \
    TWFProjectPromptsView, TWFProjectTaskSettingsView, TWFProjectCopyView, \
    TWFProjectResetView, TWFProjectUserManagementView, TWFProjectRepositorySettingsView, TWFProjectPromptEditView, \
    TWFProjectSetupView, TWFProjectTranskribusExtractView, TWFProjectTranskribusEnrichView, TWFProjectNotesView, \
    TWFProjectPromptDetailView, TWFProjectNoteEditView, TWFProjectNoteDetailView, TWFProjectPromptSettingsView, \
    TWFProjectDisplaySettingsView, TWFProjectWorkflowSettingsView
from twf.views.project.views_project_ai import TWFUnifiedAIQueryView
from twf.views.tags.views_tags import TWFProjectTagsView, TWFProjectTagsOpenView, \
    TWFProjectTagsParkedView, TWFProjectTagsResolvedView, TWFProjectTagsIgnoredView, TWFTagsDatesGroupView, \
    TWFTagsGroupView, TWFTagsOverviewView, TWFTagsAssignTagView
from twf.workflows.collection_workflows import start_review_collection_workflow
from twf.workflows.document_workflows import start_review_document_workflow

urlpatterns = [
    #############################
    # FRAMEWORK (HOME)
    path('', TWFHomeIndexView.as_view(), name='home'),
    path('about/', TWFHomeAboutView.as_view(), name='about'),
    path('login/', TWFHomeLoginView.as_view(), name='login'),
    path('logout/confirm/',
         TWFHomeView.as_view(page_title='Logout', template_name='twf/home/users/logout.html', show_context_help=False), name='user_logout'),
    path('user/profile/', TWFHomeUserProfileView.as_view(), name='user_profile'),
    path('user/change/password/', TWFHomePasswordChangeView.as_view(), name='user_change_password'),
    path('user/overview/', TWFHomeUserOverView.as_view(), name='user_overview'),
    path('logout/', auth_views.LogoutView.as_view(next_page='twf:home'), name='logout'),
    path('help/<str:view_name>/', help_content, name='help'),
    path('user/management/', TWFManageUsersView.as_view(), name='twf_user_management'),
    path('user/<int:pk>/', TWFUserDetailView.as_view(), name='user_view'),
    path('user/<int:pk>/activate/', activate_user, name='user_adm_activate'),
    path('user/<int:pk>/deactivate/', deactivate_user, name='user_adm_deactivate'),
    path('user/<int:pk>/delete/', delete_user, name='user_adm_delete'),
    path('user/<int:pk>/reset_password/', reset_password, name='user_adm_reset_password'),
    path('twf/check/system/health/', check_system_health, name='twf_check_system_health'),
    path('twf/system/health/', TWFSystemHealthView.as_view(), name='twf_system_health'),

    # Select Project
    path('projects/', TWFProjectListView.as_view(), name='project_list'),
    path('project/select/<int:pk>/confirm/', TWFSelectProjectView.as_view(), name='project_select'),
    path('project/select/<int:pk>', select_project, name='project_do_select'),
    path('project/create/', TWFCreateProjectView.as_view(), name='project_create'),
    path('projects/manage/', TWFManageProjectsView.as_view(), name='project_management'),
    path('project/delete/<int:pk>', delete_project, name='project_do_delete'),
    path('project/close/<int:pk>', close_project, name='project_do_close'),
    path('project/reopen/<int:pk>', reopen_project, name='project_do_reopen'),
    path('project/view/<int:pk>', TWFProjectViewDetailView.as_view(), name='project_view'),

    #############################
    # PROJECT
    path('project/overview/', TWFProjectOverviewView.as_view(), name='project_overview'),
    path('project/setup/tk/export/',
         TWFProjectSetupView.as_view(template_name='twf/project/setup/setup_export.html',
                                     page_title='Request Transkribus Export'), name='project_tk_export'),
    path('project/setup/tk/structure/', TWFProjectTranskribusExtractView.as_view(), name='project_tk_structure'),
    path('project/setup/tk/enrich/', TWFProjectTranskribusEnrichView.as_view(), name='project_tk_enrich'),
    path('project/setup/tk/test/', TWFProjectSetupView.as_view(template_name='twf/project/setup/test_export.html',
                                                               page_title='Test Transkribus Export'),
         name='project_test_export'),
    path('project/setup/copy/', TWFProjectCopyView.as_view(), name='project_copy'),
    path('project/setup/reset/', TWFProjectResetView.as_view(), name='project_reset'),
    path('project/setup/reset/delete/documents/', delete_all_documents, name='reset_remove_all_documents'),
    path('project/setup/reset/delete/tags/', delete_all_tags, name='reset_remove_all_tags'),
    path('project/setup/reset/delete/collections/', delete_all_collections, name='reset_remove_all_collections'),
    path('project/setup/reset/unpark/tags/', unpark_all_tags, name='reset_unpark_all_tags'),
    path('project/setup/reset/remove/prompts/', remove_all_prompts, name='reset_remove_all_prompts'),
    path('project/setup/reset/remove/tasks/', remove_all_tasks, name='reset_remove_all_tasks'),
    path('project/setup/reset/remove/dictionaries/', remove_all_dictionaries, name='reset_remove_all_dictionaries'),

    path('project/task/monitor/', TWFProjectTaskMonitorView.as_view(), name='project_task_monitor'),
    path('project/task/<int:pk>/view/', TWFProjectTaskDetailView.as_view(), name='task_detail'),

    path('project/prompts/', TWFProjectPromptsView.as_view(), name='project_prompts'),
    path('project/prompts/delete/<int:pk>/', delete_prompt, name='project_delete_prompt'),
    path('project/prompts/edit/<int:pk>/', TWFProjectPromptEditView.as_view(), name='project_edit_prompt'),
    path('project/prompt/<int:pk>/view/', TWFProjectPromptDetailView.as_view(), name='prompt_detail'),

    path('project/notes/', TWFProjectNotesView.as_view(), name='project_notes'),
    path('project/notes/<int:pk>/delete/', delete_note, name='project_notes_delete'),
    path('project/notes/<int:pk>/edit/', TWFProjectNoteEditView.as_view(), name='project_notes_edit'),
    path('project/notes/<int:pk>/view/', TWFProjectNoteDetailView.as_view(), name='project_notes_view'),

    path('project/settings/general/', TWFProjectGeneralSettingsView.as_view(), name='project_settings_general'),
    path('project/settings/credentials/', TWFProjectCredentialsSettingsView.as_view(),
         name='project_settings_credentials'),
    path('project/settings/tasks/', TWFProjectTaskSettingsView.as_view(), name='project_settings_tasks'),
    path('project/settings/prompt/', TWFProjectPromptSettingsView.as_view(), name='project_settings_prompt'),
    path('project/settings/repositories/', TWFProjectRepositorySettingsView.as_view(),
         name='project_settings_repository'),
    path('project/settings/display/', TWFProjectDisplaySettingsView.as_view(), name='project_settings_display'),
    path('project/settings/workflows/', TWFProjectWorkflowSettingsView.as_view(), name='project_settings_workflows'),
    path('project/user/management/', TWFProjectUserManagementView.as_view(), name='user_management'),
    # Redirect permissions URL to the user management view
    path('project/permissions/', TWFProjectUserManagementView.as_view(), name='user_roles'),
    path('project/<int:project_id>/permissions/update/<int:user_id>/', update_user_permissions, name='update_user_permissions'),

    # Project options
    path('project/query/', TWFProjectQueryView.as_view(), name='project_query'),
    # Unified AI query view
    path('project/ai/query/', TWFUnifiedAIQueryView.as_view(), name='project_ai_query_unified'),


    #############################
    # DOCUMENTS
    path('documents/', TWFDocumentsOverviewView.as_view(), name='documents_overview'),
    path('documents/browse/', TWFDocumentsBrowseView.as_view(), name='documents_browse'),
    path('documents/search/', TWFDocumentsSearchView.as_view(), name='documents_search'),
    path('documents/review/', TWFDocumentReviewView.as_view(), name='documents_review'),
    path('documents/name/', TWFDocumentNameView.as_view(), name='name_documents'),
    path('document/<int:pk>/', TWFDocumentDetailView.as_view(), name='view_document'),

    # Unified AI batch view
    path('documents/batch/ai/', TWFUnifiedDocumentBatchView.as_view(), name='documents_batch_ai_unified'),

    #############################
    # TAGS
    path('tags/overview/', TWFTagsOverviewView.as_view(), name='tags_overview'),
    path('tags/all/', TWFProjectTagsView.as_view(template_name='twf/tags/all_tags.html',
                                                 page_title='All Tags'),
         name='tags_all'),
    path('tags/group/', TWFTagsGroupView.as_view(), name='tags_group'),
    path('tags/assign/<int:pk>/', TWFTagsAssignTagView.as_view(), name='tags_assign'),
    path('tags/dates/', TWFTagsDatesGroupView.as_view(), name='tags_dates'),
    # Tag views
    path('tags/view/parked/', TWFProjectTagsParkedView.as_view(), name='tags_view_parked'),
    path('tags/view/open/', TWFProjectTagsOpenView.as_view(), name='tags_view_open'),
    path('tags/view/resolved/', TWFProjectTagsResolvedView.as_view(), name='tags_view_resolved'),
    path('tags/view/ignored/', TWFProjectTagsIgnoredView.as_view(), name='tags_view_ignored'),
    # Park and unpark tags
    path('tags/park/<int:pk>/', park_tag, name='tags_park'),
    path('tags/park-all/<int:pk>/', park_all_identical_tags, name='tags_park_all'),
    path('tags/unpark/<int:pk>/', unpark_tag, name='tags_unpark'),
    path('tags/ungroup/<int:pk>/', ungroup_tag, name='tags_ungroup'),
    path('tags/delete/<int:pk>/', delete_tag, name='tags_delete'),


    #############################
    # DICTIONARIES
    path('dictionaries/overview', TWFDictionaryOverviewView.as_view(), name='dictionaries_overview'),
    path('dictionaries/', TWFDictionaryDictionariesView.as_view(), name='dictionaries'),
    path('dictionaries/add/', TWFDictionaryAddView.as_view(), name='dictionaries_add'),
    path('dictionaries/add/<int:pk>/', add_dictionary_to_project, name='dictionaries_add_to_project'),
    path('dictionaries/remove/<int:pk>/', remove_dictionary_from_project, name='dictionaries_remove_from_project'),
    path('dictionaries/create/', TWFDictionaryCreateView.as_view(), name='dictionary_create'),
    path('dictionaries/<int:pk>/', TWFDictionaryDictionaryView.as_view(), name='dictionaries_view'),
    path('dictionaries/<int:pk>/edit/', TWFDictionaryDictionaryEditView.as_view(), name='dictionaries_edit'),

    path('dictionaries/entry/<int:pk>/', TWFDictionaryDictionaryEntryView.as_view(), name='dictionaries_entry_view'),
    path('dictionaries/entry/<int:pk>/skip/', skip_entry, name='dictionaries_entry_skip'),
    path('dictionaries/entry/<int:pk>/edit/',
         TWFDictionaryDictionaryEntryEditView.as_view(), name='dictionaries_entry_edit'),
    path('dictionaries/entry/<int:pk>/delete/', delete_dictionary_entry, name='dictionaries_entry_delete'),
    path('dictionaries/normalization/wizard/', TWFDictionaryNormDataView.as_view(), name='dictionaries_normalization'),
    path('dictionaries/merge/entries/', TWFDictionaryMergeEntriesView.as_view(), name='dictionaries_entry_merging'),
    path('dictionaries/variations/delete/<int:pk>/', delete_variation, name='dictionaries_delete_variation'),

    path('dictionaries/batch/gnd/', TWFDictionaryGNDBatchView.as_view(), name='dictionaries_batch_gnd'),
    path('dictionaries/batch/geonames/', TWFDictionaryGeonamesBatchView.as_view(), name='dictionaries_batch_geonames'),
    path('dictionaries/batch/wikidata/', TWFDictionaryWikidataBatchView.as_view(), name='dictionaries_batch_wikidata'),
    # Unified AI batch view
    path('dictionaries/batch/ai/', TWFUnifiedDictionaryAIBatchView.as_view(),
         name='dictionaries_batch_ai_unified'),

    path('dictionaries/request/gnd/', TWFDictionaryGNDRequestView.as_view(), name='dictionaries_request_gnd'),
    path('dictionaries/request/geonames/', TWFDictionaryGeonamesRequestView.as_view(),
         name='dictionaries_request_geonames'),
    path('dictionaries/request/wikidata/', TWFDictionaryWikidataRequestView.as_view(),
         name='dictionaries_request_wikidata'),
    # Unified AI request view
    path('dictionaries/request/ai/', TWFUnifiedDictionaryAIRequestView.as_view(),
         name='dictionaries_request_ai_unified'),

    #############################
    # COLLECTIONS
    path('collections/', TWFCollectionOverviewView.as_view(), name='collections'),
    path('collections/list/', TWFCollectionListView.as_view(), name='collections_view'),
    path('collections/create/', TWFCollectionsCreateView.as_view(), name='project_collections_create'),
    path('collections/<int:pk>/', TWFCollectionsDetailView.as_view(), name='collection_view'),
    path('collections/review/', TWFCollectionsReviewView.as_view(), name='collections_review'),
    # Unified AI batch view
    path('collections/batch/ai/', TWFUnifiedCollectionAIBatchView.as_view(), name='collections_batch_ai_unified'),
    # Unified AI request view
    path('collections/request/ai/', TWFUnifiedCollectionAIRequestView.as_view(), name='collections_request_ai_unified'),

    path('collections/delete/<int:collection_id>/', delete_collection, name='collection_delete'),
    path('collections/edit/<int:pk>/', TWFCollectionsEditView.as_view(), name='collection_edit'),

    path('collections/item/<int:pk>/', TWFCollectionItemView.as_view(), name='collection_item_view'),
    path('collections/item/edit/<int:pk>/', TWFCollectionItemEditView.as_view(), name='collection_item_edit'),
    path('collections/item/copy/<int:pk>/', copy_collection_item, name='collection_item_copy'),
    path('collections/item/delete/<int:pk>/', delete_collection_item, name='collection_item_delete'),
    path('collections/item/download/txt/<int:pk>/', download_collection_item_txt, name='collection_item_download_txt'),
    path('collections/item/download/json/<int:pk>/', download_collection_item_json, name='collection_item_download_json'),
    path('collections/item/split/<int:pk>/<int:index>/', split_collection_item, name='collection_item_split'),
    path('collections/item/delete/anno/<int:pk>/<int:index>/', delete_collection_item_annotation, name='collection_item_delete_annotation'),
    path('collections/item/set_status/<int:pk>/open/', set_col_item_status_open, name='collection_item_status_open'),
    path('collections/item/set_status/<int:pk>/reviewed/', set_col_item_status_reviewed, name='collection_item_status_reviewed'),
    path('collections/item/set_status/<int:pk>/faulty/', set_col_item_status_faulty, name='collection_item_status_faulty'),
    path('collections/<int:pk>/add/document', TWFCollectionsAddDocumentView.as_view(), name='collection_add_document'),

    #############################
    # EXPORT
    path('export/', TWFExportOverviewView.as_view(), name='export_overview'),
    path('export/exports/', TWFExportListView.as_view(), name='export_view_exports'),
    path('export/exports/<int:pk>/delete/', delete_export, name='export_exports_delete'),


    path('export/run/', TWFExportRunView.as_view(), name='export_run'),
    path('export/project/', TWFExportProjectView.as_view(), name='export_project'),

    path('export/zenodo/', TWFExportZenodoView.as_view(), name='export_to_zenodo'),
    path('export/zenodo/upload/<int:export_id>/', TWFExportZenodoVersionView.as_view(), name='zenodo_upload'),
    path('export/zenodo/disconnect/', disconnect_zenodo, name='zenodo_disconnect'),
    path('export/zenodo/connect/<str:deposition_id>/', connect_zenodo, name='zenodo_connect'),
    path('export/zenodo/new/connection/', create_zenodo_connection, name='zenodo_create_connection'),

    path('export/configurations/', TWFExportConfListView.as_view(), name='export_view_export_confs'),
    path('export/configuration/', TWFExportConfigurationView.as_view(), name='export_configure'),
    path('export/configuration/<int:pk>/edit/', TWFExportConfigurationView.as_view(), name='export_configure_edit'),
    path('export/configuration/<int:pk>/view/sample/', TWFExportSampleView.as_view(), name='export_configure_view_sample'),
    path('export/configuration/<int:pk>/delete/', delete_export_configuration, name='export_conf_delete'),

    path('import/dictionaries/', TWFImportDictionaryView.as_view(), name='import_dictionaries'),

    #############################
    # WORKFLOWS
    path('workflows/documents/review/start/', start_review_document_workflow, name='start_review_document_workflow'),
    path('workflows/collection/review/start/<int:collection_id>/', start_review_collection_workflow,
         name='start_review_collection_workflow'),

    #############################
    # CELERY TASKS
    path('celery/status/<str:task_id>/', task_status_view, name='celery_task_status'),
    path('celery/cancel/<str:task_id>/', task_cancel_view, name='celery_task_cancel'),
    path('celery/remove/<str:task_id>/', task_remove_view, name='celery_task_remove'),

    path('celery/transkribus/extract/', start_extraction, name='task_transkribus_extract_export'),
    path('celery/transkribus/enrich/', start_enrich_metadata, name='task_transkribus_enrich_metadata'),
    path('celery/transkribus/enrich/document/<int:document_pk>/', start_enrich_document_metadata, name='task_enrich_document_metadata'),
    path('celery/project/copy/', start_copy_project, name='task_project_copy'),

    # Unified AI query task trigger
    path('celery/project/query/ai/', start_query_project_unified, name='task_project_query_unified'),

    path('celery/metadata/sheets/load/', start_sheet_metadata, name='task_metadata_load_sheets'),
    path('celery/metadata/json/load/', start_json_metadata, name='task_metadata_load_json'),

    # Unified AI batch task trigger
    path('celery/documents/batch/ai/', start_documents_batch_unified, name='task_documents_batch_unified'),

    path('celery/dictionaries/batch/gnd/', start_dict_gnd_batch, name='task_dictionaries_batch_gnd'),
    path('celery/dictionaries/batch/geonames/', start_dict_geonames_batch, name='task_dictionaries_batch_geonames'),
    path('celery/dictionaries/batch/wikidata/', start_dict_wikidata_batch, name='task_dictionaries_batch_wikidata'),
    # Unified AI batch task trigger
    path('celery/dictionaries/batch/ai/', start_dictionaries_batch_unified, name='task_dictionaries_batch_unified'),

    path('celery/dictionaries/request/gnd/', start_dict_gnd_request, name='task_dictionaries_request_gnd'),
    path('celery/dictionaries/request/geonames/', start_dict_geonames_request, name='task_dictionaries_request_geonames'),
    path('celery/dictionaries/request/wikidata/', start_dict_wikidata_request, name='task_dictionaries_request_wikidata'),
    # Unified AI request task trigger
    path('celery/dictionaries/request/ai/', start_dictionaries_request_unified, name='task_dictionaries_request_unified'),

    # Unified AI batch task trigger
    path('celery/collections/batch/ai/', start_collections_batch_unified, name='task_collections_batch_unified'),
    # Unified AI request task trigger
    path('celery/collections/request/ai/', start_collections_request_unified, name='task_collections_request_unified'),

    path('celery/export/run/', start_export, name='task_export'),
    path('celery/export/project/', start_export_project, name='task_export_project'),
    path('celery/export/zenodo/', start_export_to_zenodo, name='task_export_zenodo'),

    #############################
    # AJAX CALLS
    path('ajax/transkribus/export/request/', ajax_transkribus_request_export,
         name='ajax_transkribus_request_export'),
    path('ajax/transkribus/export/reset/', ajax_transkribus_reset_export,
         name='ajax_transkribus_reset_export'),
    path('ajax/transkribus/export/status/', ajax_transkribus_request_export_status,
         name='ajax_transkribus_request_export__status'),
    path('ajax/transkribus/export/start/download/', ajax_transkribus_download_export,
         name='ajax_transkribus_download_export'),
    path('ajax/transkribus/export/monitor/download/', download_progress_view,
         name='download_progress'),
    path('ajax/markdown-generate/', ajax_markdown_generate,
         name='ajax_markdown_generate'),
    path('ajax/markdown-preview/', ajax_markdown_preview,
         name='ajax_markdown_preview'),
    path('ajax/load/prompt/', load_prompt, name='ajax_load_prompt'),
    path('ajax/save/prompt/', save_prompt, name='ajax_save_prompt'),
    path('ajax/get/prompts/', get_prompts, name='ajax_get_prompts'),
    path('ajax/save/ai_result_as_note/', save_ai_result_as_note, name='ajax_save_ai_result_as_note'),

    #############################
    # METADATA
    path('metadata/overview/', TWFMetadataOverviewView.as_view(), name='metadata_overview'),

    path('metadata/load/metadata/', TWFMetadataLoadDataView.as_view(), name='metadata_load_metadata'),
    path('metadata/load/sheets/metadata/', TWFMetadataLoadSheetsDataView.as_view(),
         name='metadata_load_sheets_metadata'),
    path('metadata/extract/tags/', TWFMetadataExtractTagsView.as_view(), name='metadata_extract'),

    path('metadata/review/documents/', TWFMetadataReviewDocumentsView.as_view(), name='metadata_review_documents'),
    path('metadata/review/pages/', TWFMetadataReviewPagesView.as_view(), name='metadata_review_pages'),

    path('metadata/update/document/<int:pk>/<str:base_key>/', update_document_metadata, name='update_document_metadata'),
    path('metadata/update/collection-item/<int:pk>/<str:base_key>/', update_collection_item_metadata, name='update_collection_item_metadata'),
    path('metadata/update/dictionaryentry/<int:pk>/<str:base_key>/', update_dictionary_entry_metadata, name='update_dictionary_entry_metadata'),

    path('metadata/delete/document/<int:pk>/<str:base_key>/', delete_document_metadata, name='update_document_metadata'),
    path('metadata/delete/collection-item/<int:pk>/<str:base_key>/', delete_collection_item_metadata, name='update_collection_item_metadata'),
    path('metadata/delete/dictionaryentry/<int:pk>/<str:base_key>/', delete_dictionary_entry_metadata, name='delete_dictionary_entry_metadata'),

    path('dictionaries/entry/<int:pk>/metadata/json/', save_entry_metadata_json, name='dictionaries_entry_save_json'),

    path('celery/dictionaries/entry/enrich/geonames/', start_enrich_entry_geonames, name='task_enrich_entry_geonames'),
    path('celery/dictionaries/entry/enrich/gnd/', start_enrich_entry_gnd, name='task_enrich_entry_gnd'),
    path('celery/dictionaries/entry/enrich/wikidata/', start_enrich_entry_wikidata, name='task_enrich_entry_wikidata'),
    path('celery/dictionaries/entry/enrich/ai/', start_enrich_entry_ai, name='task_enrich_entry_ai'),

    path('dictionaries/entry/<int:pk>/search/geonames/', search_entry_geonames, name='search_entry_geonames'),
    path('dictionaries/entry/<int:pk>/search/gnd/', search_entry_gnd, name='search_entry_gnd'),
    path('dictionaries/entry/<int:pk>/search/wikidata/', search_entry_wikidata, name='search_entry_wikidata'),
    path('dictionaries/entry/<int:pk>/lookup/save/', save_entry_lookup, name='save_entry_lookup'),

    path('validate_page_field/', validate_page_field, name='validate_page_field'),
    path('validate_page_field/', validate_document_field, name='validate_document_field'),
]
