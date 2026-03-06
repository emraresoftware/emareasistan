# 📁 Emare Asistan — Dosya Yapısı

> **Oluşturulma:** Otomatik  
> **Amaç:** Yapay zekalar kod yazmadan önce mevcut dosya yapısını incelemeli

---

## Proje Dosya Ağacı

```
/Users/emre/Desktop/Emare/emareasistan
├── .DS_Store
├── .cursor
│   └── rules
│       └── devam-workflow.mdc
├── .cursorignore
├── .dockerignore
├── .env
├── .env.example
├── .gitignore
├── .venv_backup_broken
│   ├── .DS_Store
│   ├── .gitignore
│   ├── bin
│   │   ├── Activate.ps1
│   │   ├── activate
│   │   ├── activate.csh
│   │   ├── activate.fish
│   │   ├── alembic
│   │   ├── celery
│   │   ├── distro
│   │   ├── dotenv
│   │   ├── f2py
│   │   ├── fastapi
│   │   ├── httpx
│   │   ├── jsondiff
│   │   ├── jsonpatch
│   │   ├── jsonpointer
│   │   ├── mako-render
│   │   ├── normalizer
│   │   ├── numpy-config
│   │   ├── openai
│   │   ├── python -> python3.14
│   │   ├── python3 -> python3.14
│   │   ├── python3.14 -> /usr/local/Cellar/python@3.14/3.14.2/Frameworks/Python.framework/Versions/3.14/bin/python3.14
│   │   ├── tqdm
│   │   ├── uvicorn
│   │   ├── watchfiles
│   │   ├── websockets
│   │   └── 𝜋thon -> python3.14
│   ├── include
│   │   └── site
│   │       └── python3.14
│   ├── lib
│   │   ├── .DS_Store
│   │   └── python3.14
│   │       ├── .DS_Store
│   │       └── site-packages
│   └── pyvenv.cfg
├── .vscode
│   └── settings.json
├── CURSOR_STABILITY.md
├── DEPLOY.md
├── DESIGN_GUIDE.md
├── DEVAM.md
├── DOSYA_YAPISI.md
├── Dockerfile
├── EMAREASISTAN_HAFIZA.md
├── EMARE_AI_COLLECTIVE.md
├── EMARE_ANAYASA.md
├── EMARE_ORTAK_CALISMA -> /Users/emre/Desktop/Emare/EMARE_ORTAK_CALISMA
├── EMARE_ORTAK_HAFIZA.md
├── HATA_AYIKLAMA.md
├── KIVILCIM.md
├── KIVILCIM_RAPOR.md
├── README.md
├── V2.md
├── WORKSPACE_HAFIFLATMA.md
├── admin
│   ├── PERFORMANCE.md
│   ├── __init__.py
│   ├── common.py
│   ├── helpers.py
│   ├── partner.py
│   ├── routes.py
│   ├── routes_agent.py
│   ├── routes_auth.py
│   ├── routes_dashboard.py
│   ├── routes_orders.py
│   ├── routes_partner_super.py
│   ├── routes_rules_workflows.py
│   ├── routes_settings.py
│   ├── routes_trendyol.py
│   └── templates
│       ├── admin_staff_invoices.html
│       ├── admin_staff_leaves.html
│       ├── admin_staff_purchase_orders.html
│       ├── agent_chat.html
│       ├── agent_panel.html
│       ├── album_form.html
│       ├── albums.html
│       ├── analytics.html
│       ├── appointments_list.html
│       ├── base.html
│       ├── cargo_list.html
│       ├── chat_audits.html
│       ├── contacts_list.html
│       ├── conversation_detail.html
│       ├── conversations.html
│       ├── dashboard.html
│       ├── export_template_form.html
│       ├── export_templates_list.html
│       ├── instagram_dashboard.html
│       ├── instagram_setup.html
│       ├── login.html
│       ├── login_choose_partner.html
│       ├── order_detail.html
│       ├── orders.html
│       ├── partner_admin.html
│       ├── partner_base.html
│       ├── partner_branding.html
│       ├── partner_deploy.html
│       ├── partner_modules.html
│       ├── partner_panel.html
│       ├── partner_tenant_branding.html
│       ├── partner_users.html
│       ├── process_config_form.html
│       ├── process_config_list.html
│       ├── product_form.html
│       ├── products.html
│       ├── products_gallery.html
│       ├── quick_replies.html
│       ├── register.html
│       ├── register_confirm.html
│       ├── register_sent.html
│       ├── reminder_form.html
│       ├── reminders_list.html
│       ├── rule_form.html
│       ├── rules.html
│       ├── settings_account.html
│       ├── settings_account_super.html
│       ├── settings_ai.html
│       ├── settings_api.html
│       ├── settings_branding.html
│       ├── settings_index.html
│       ├── settings_web_chat.html
│       ├── super_admin.html
│       ├── super_admin_login_logs.html
│       ├── super_admin_modules.html
│       ├── super_admin_user_status.html
│       ├── training_form.html
│       ├── training_import.html
│       ├── training_list.html
│       ├── trendyol_dashboard.html
│       ├── users_list.html
│       ├── video_form.html
│       ├── videos_list.html
│       ├── web_chat.html
│       ├── whatsapp_list.html
│       ├── workflow_builder.html
│       ├── workflow_form.html
│       └── workflows_list.html
├── alembic
│   ├── README
│   ├── env.py
│   ├── script.py.mako
│   └── versions
│       ├── 001_initial_schema.py
│       ├── 002_pgvector_extension.py
│       ├── 003_audit_log.py
│       ├── 004_ai_training_trigger_keywords.py
│       ├── 005_message_feedback.py
│       ├── 006_products_tenant_id.py
│       ├── 007_products_fts.py
│       ├── 008_abandoned_cart_reminder.py
│       ├── 009_tenant_settings_table.py
│       ├── 010_appointments.py
│       ├── 011_admin_staff_tables.py
│       ├── 011_proactive_message_tracking.py
│       ├── 013_export_templates.py
│       ├── 014_tenant_workflows.py
│       ├── 015_chat_audits.py
│       ├── 016_workflow_graph_layout.py
│       ├── 017_quick_replies.py
│       ├── 018_partners.py
│       ├── 019_users_last_login.py
│       ├── 020_users_last_seen.py
│       ├── 021_user_phone_notifications.py
│       └── 022_conversation_csat.py
├── alembic.ini
├── asistan-hafif.code-workspace
├── asistan.db
├── asistan.log
├── asistan_start.log
├── bridge.log
├── bridge_start.log
├── celery_app.py
├── client_secret_973218723100-2tfn5mvlqq5c9g4tcce7g11gfgmuomei.apps.googleusercontent.com.json
├── config
│   ├── __init__.py
│   └── settings.py
├── core
├── data
│   ├── app_settings.json
│   ├── products_sample.json
│   ├── products_scraped.json
│   ├── quick_replies.json
│   ├── tenant6_training.json
│   ├── tenants
│   │   ├── anasayfa
│   │   │   └── products.json
│   │   ├── cihan-biliim-hizmetleri-mikrotik-ve-ubnt-yetkili-s
│   │   │   └── products.json
│   │   ├── cihan-bilisim-panel
│   │   │   └── products.json
│   │   ├── cihan-bilisim-panel-3
│   │   │   └── products.json
│   │   ├── cihan-bilisim-panel-3-1
│   │   │   └── products.json
│   │   ├── defence-360-panel
│   │   │   └── products.json
│   │   ├── demo-5321112233-8382
│   │   │   └── products.json
│   │   ├── doa-telekom
│   │   │   └── products.json
│   │   ├── doğa-telekom-panel
│   │   │   └── products.json
│   │   ├── efor-bioteknoloji
│   │   │   └── products.json
│   │   ├── examplecom
│   │   │   └── products.json
│   │   ├── galen
│   │   │   └── products.json
│   │   ├── gökhan-panel
│   │   │   └── products.json
│   │   ├── httpswwwfazdanismanlikcom
│   │   │   └── products.json
│   │   ├── oto-klf
│   │   │   └── products.json
│   │   ├── öner-acar-panel
│   │   │   └── products.json
│   │   ├── piramit-bilgisayar-panel
│   │   │   └── products.json
│   │   ├── test
│   │   │   └── products.json
│   │   ├── test-11
│   │   │   └── products.json
│   │   ├── test-12
│   │   │   └── products.json
│   │   ├── test-ba3eb6
│   │   │   └── products.json
│   │   ├── test-firma
│   │   │   └── products.json
│   │   ├── test1-test
│   │   │   └── products.json
│   │   └── tugva-yurt
│   │       └── products.json
│   └── vehicle_models.json
├── deploy
│   ├── README.md
│   ├── asistan-health-check.sh
│   ├── install-services.sh
│   ├── systemd
│   │   ├── asistan-api.service
│   │   ├── asistan-whatsapp.service
│   │   └── asistan-whatsapp@.service
│   └── update-bridge.sh
├── deploy.sh
├── deploy_keys
├── docker-compose.bridge.yml
├── docker-compose.yml
├── docs
│   ├── 01_GENEL.md
│   ├── 02_KULLANIM.md
│   ├── 03_MIMARI.md
│   ├── 04_TEKNIK.md
│   ├── 05_OPERASYON.md
│   ├── EMARE_ASISTAN.md
│   └── emare_sunum.html
├── full-deploy.sh
├── integrations
│   ├── __init__.py
│   ├── bridge_api.py
│   ├── channels
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── instagram_channel.py
│   │   ├── manager.py
│   │   ├── telegram_channel.py
│   │   └── whatsapp_cloud.py
│   ├── chat_handler.py
│   ├── cron_api.py
│   ├── handlers
│   │   ├── __init__.py
│   │   ├── appointment_handler.py
│   │   ├── cargo_handler.py
│   │   ├── human_handler.py
│   │   ├── order_handler.py
│   │   └── product_handler.py
│   ├── instagram_webhook.py
│   ├── support_chat_api.py
│   ├── telegram_bot.py
│   ├── web_chat_api.py
│   ├── whatsapp_qr.py
│   └── whatsapp_webhook.py
├── main.py
├── middleware
│   ├── __init__.py
│   ├── admin_context.py
│   ├── rate_limit.py
│   └── security_headers.py
├── models
│   ├── __init__.py
│   ├── ai_training.py
│   ├── appointment.py
│   ├── audit_log.py
│   ├── chat_audit.py
│   ├── contact.py
│   ├── conversation.py
│   ├── database.py
│   ├── embedding.py
│   ├── export_template.py
│   ├── image_album.py
│   ├── invoice.py
│   ├── leave_request.py
│   ├── message_feedback.py
│   ├── order.py
│   ├── partner.py
│   ├── pending_registration.py
│   ├── product.py
│   ├── purchase_order.py
│   ├── quick_reply.py
│   ├── reminder.py
│   ├── response_rule.py
│   ├── tenant.py
│   ├── tenant_setting.py
│   ├── tenant_workflow.py
│   ├── user.py
│   ├── video.py
│   └── whatsapp_connection.py
├── pytest.ini
├── remote-update.sh
├── requirements.txt
├── run.py
├── scraper
│   ├── __init__.py
│   └── meridyen_scraper.py
├── scripts
│   ├── add_docstrings.py
│   ├── archive
│   │   ├── check_defence360.py
│   │   ├── create_piramit_vpn_workflow.py
│   │   ├── export_tenant6_training.py
│   │   ├── import_tenant6_training.py
│   │   ├── load_tenant6_quick_replies.py
│   │   ├── load_tenant6_rules.py
│   │   ├── repair_meridyen.py
│   │   ├── setup_defence360.py
│   │   └── sync_tenant6_training_to_server.sh
│   ├── assign_tenant_to_partner.py
│   ├── check-server.sh
│   ├── check_support_chat_create_rule.py
│   ├── check_whatsapp.py
│   ├── cleanup.sh
│   ├── create_sample_album.py
│   ├── deploy_single_tenant.sh
│   ├── enable_web_chat_tenant.py
│   ├── fix_tenant_check.py
│   ├── fix_whatsapp.py
│   ├── generate_scenario_images.py
│   ├── kivilcim.py
│   ├── list_tenants_partners.py
│   ├── live_chat_monitor.py
│   ├── local_llm
│   │   ├── README.md
│   │   ├── chat.py
│   │   ├── extract_training_data.py
│   │   ├── prepare_dataset.py
│   │   ├── requirements.txt
│   │   ├── retrain.sh
│   │   ├── sample_train.jsonl
│   │   └── train_lora.py
│   ├── migrate_uploads_to_tenant_folders.py
│   ├── remote_deploy_tenant.sh
│   ├── reset_agent_takeover.py
│   ├── scrape_products.py
│   ├── seed_emare_asistan_training.py
│   ├── seed_training_examples.py
│   ├── server-setup.sh
│   ├── show_recent_chats.py
│   ├── sync_db_from_server.sh
│   ├── sync_training_to_local_llm.py
│   └── test_support_chat.py
├── services
│   ├── __init__.py
│   ├── ai
│   │   ├── assistant.py
│   │   ├── embeddings.py
│   │   ├── indexer.py
│   │   ├── ocr.py
│   │   ├── rag.py
│   │   ├── stt.py
│   │   ├── tts.py
│   │   ├── vector_store.py
│   │   ├── vision.py
│   │   └── website_analyzer.py
│   ├── appointment
│   │   └── service.py
│   ├── core
│   │   ├── __init__.py
│   │   ├── audit.py
│   │   ├── cache.py
│   │   ├── crypto.py
│   │   ├── module_config.py
│   │   ├── modules.py
│   │   ├── settings.py
│   │   ├── state_machine.py
│   │   ├── tenant.py
│   │   ├── tenant_settings.py
│   │   ├── time_utils.py
│   │   └── tracing.py
│   ├── integration
│   │   ├── email.py
│   │   └── sync.py
│   ├── modules.py
│   ├── notifications
│   │   ├── __init__.py
│   │   └── user_notifier.py
│   ├── order
│   │   ├── abandoned_cart.py
│   │   ├── cargo.py
│   │   ├── payment.py
│   │   └── service.py
│   ├── pipeline
│   ├── product
│   │   ├── importer.py
│   │   ├── service.py
│   │   └── vehicles.py
│   ├── trendyol
│   │   ├── __init__.py
│   │   ├── api.py
│   │   ├── questions.py
│   │   └── sync.py
│   ├── whatsapp
│   │   ├── agent.py
│   │   ├── audit.py
│   │   ├── escalation.py
│   │   └── health.py
│   └── workflow
│       ├── engine.py
│       ├── export.py
│       ├── export_trigger.py
│       ├── metrics.py
│       ├── pipeline
│       │   ├── __init__.py
│       │   ├── formatter.py
│       │   ├── intent_detector.py
│       │   ├── pipeline.py
│       │   ├── router.py
│       │   └── sanitizer.py
│       ├── proactive.py
│       ├── rules.py
│       └── service.py
├── sohbetler_20260215_1905.txt
├── sohbetler_20260215_1956.txt
├── start.sh
├── static
│   ├── index.html
│   ├── index.html.bak
│   └── index.html.bak2
├── tasks.py
├── tests
│   ├── conftest.py
│   ├── test_channels.py
│   ├── test_modules.py
│   └── test_smoke.py
├── trendyol_bot_kozmo
│   ├── .env
│   ├── .env.example
│   ├── DESIGN_GUIDE copy.md
│   ├── DESIGN_GUIDE.md
│   ├── EMARE_AI_COLLECTIVE.md
│   ├── EMARE_ORTAK_HAFIZA.md
│   ├── api
│   │   ├── __init__.py
│   │   ├── gemini.py
│   │   └── trendyol.py
│   ├── app.log
│   ├── app_settings.json
│   ├── automated_responses.json
│   ├── config.py
│   ├── core
│   │   ├── __init__.py
│   │   ├── data.py
│   │   ├── matcher.py
│   │   ├── metrics.py
│   │   └── processor.py
│   ├── kozmopol.log
│   ├── kozmopol.py
│   ├── kozmopol_v1_backup.py
│   ├── kozmopol_v2_backup.py
│   ├── kozmopol_v3_monolith_backup.py
│   ├── main.py
│   ├── pending_questions.json
│   ├── question_log.json
│   ├── requirements.txt
│   ├── response_templates.json
│   ├── ui
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── dialogs.py
│   │   ├── tab_ai.py
│   │   ├── tab_log.py
│   │   ├── tab_orders.py
│   │   ├── tab_pending.py
│   │   ├── tab_responses.py
│   │   ├── tab_reviews.py
│   │   ├── tab_settings.py
│   │   ├── tab_stats.py
│   │   └── tab_templates.py
│   └── word_blacklist.json
├── update.sh
├── uploads
│   ├── albums
│   ├── branding
│   │   └── partner_5
│   │       ├── logo_3aee12ce002a.png
│   │       └── logo_af088241adfe.png
│   └── videos
└── whatsapp-bridge
    ├── .asistan.pid
    ├── .dockerignore
    ├── .env.example
    ├── .gitignore
    ├── .wwebjs_auth
    │   └── session
    │       ├── ActorSafetyLists
    │       ├── AmountExtractionHeuristicRegexes
    │       ├── BrowserMetrics-spare.pma
    │       ├── CertificateRevocation
    │       ├── ChromeFeatureState
    │       ├── Crowd Deny
    │       ├── Default
    │       ├── DevToolsActivePort
    │       ├── FileTypePolicies
    │       ├── FirstPartySetsPreloaded
    │       ├── GrShaderCache
    │       ├── GraphiteDawnCache
    │       ├── HistorySearch
    │       ├── Last Version
    │       ├── Local State
    │       ├── MEIPreload
    │       ├── NativeMessagingHosts
    │       ├── OnDeviceHeadSuggestModel
    │       ├── OriginTrials
    │       ├── PKIMetadata
    │       ├── PlusAddressBlocklist
    │       ├── PrivacySandboxAttestationsPreloaded
    │       ├── RunningChromeVersion -> 145.0.7632.46:1
    │       ├── SSLErrorAssistant
    │       ├── Safe Browsing
    │       ├── SafetyTips
    │       ├── ShaderCache
    │       ├── SingletonCookie -> 9862498318357834859
    │       ├── SingletonLock -> Emre-MacBook-Pro.local-72188
    │       ├── SingletonSocket -> /var/folders/23/jrz_jjlj0t916n3sv1_xxmdr0000gn/T/com.google.chrome.for.testing.vcd7cj/SingletonSocket
    │       ├── Subresource Filter
    │       ├── TpcdMetadata
    │       ├── TrustTokenKeyCommitments
    │       ├── Variations
    │       ├── WasmTtsEngine
    │       ├── WidevineCdm
    │       ├── ZxcvbnData
    │       ├── component_crx_cache
    │       ├── extensions_crx_cache
    │       ├── first_party_sets.db
    │       ├── first_party_sets.db-journal
    │       └── segmentation_platform
    ├── .wwebjs_auth_conn_0dbbc9bc
    │   └── session
    │       ├── ActorSafetyLists
    │       ├── AmountExtractionHeuristicRegexes
    │       ├── CertificateRevocation
    │       ├── ChromeFeatureState
    │       ├── Crowd Deny
    │       ├── Default
    │       ├── DevToolsActivePort
    │       ├── FileTypePolicies
    │       ├── FirstPartySetsPreloaded
    │       ├── GrShaderCache
    │       ├── GraphiteDawnCache
    │       ├── HistorySearch
    │       ├── Last Version
    │       ├── Local State
    │       ├── MEIPreload
    │       ├── NativeMessagingHosts
    │       ├── OnDeviceHeadSuggestModel
    │       ├── OriginTrials
    │       ├── PKIMetadata
    │       ├── PlusAddressBlocklist
    │       ├── PrivacySandboxAttestationsPreloaded
    │       ├── RunningChromeVersion -> 145.0.7632.46:1
    │       ├── SSLErrorAssistant
    │       ├── Safe Browsing
    │       ├── SafetyTips
    │       ├── ShaderCache
    │       ├── SingletonCookie -> 3727319895529283633
    │       ├── SingletonLock -> Emre-MacBook-Pro.local-86617
    │       ├── SingletonSocket -> /var/folders/23/jrz_jjlj0t916n3sv1_xxmdr0000gn/T/com.google.chrome.for.testing.GjcgiS/SingletonSocket
    │       ├── Subresource Filter
    │       ├── TpcdMetadata
    │       ├── TrustTokenKeyCommitments
    │       ├── Variations
    │       ├── WasmTtsEngine
    │       ├── WidevineCdm
    │       ├── ZxcvbnData
    │       ├── component_crx_cache
    │       ├── extensions_crx_cache
    │       ├── first_party_sets.db
    │       ├── first_party_sets.db-journal
    │       └── segmentation_platform
    ├── .wwebjs_auth_conn_12817af3
    │   └── session
    │       ├── ActorSafetyLists
    │       ├── AmountExtractionHeuristicRegexes
    │       ├── BrowserMetrics-spare.pma
    │       ├── CertificateRevocation
    │       ├── ChromeFeatureState
    │       ├── Crowd Deny
    │       ├── Default
    │       ├── DevToolsActivePort
    │       ├── FileTypePolicies
    │       ├── FirstPartySetsPreloaded
    │       ├── GrShaderCache
    │       ├── GraphiteDawnCache
    │       ├── HistorySearch
    │       ├── Last Version
    │       ├── Local State
    │       ├── MEIPreload
    │       ├── NativeMessagingHosts
    │       ├── OnDeviceHeadSuggestModel
    │       ├── OriginTrials
    │       ├── PKIMetadata
    │       ├── PlusAddressBlocklist
    │       ├── PrivacySandboxAttestationsPreloaded
    │       ├── SSLErrorAssistant
    │       ├── Safe Browsing
    │       ├── SafetyTips
    │       ├── ShaderCache
    │       ├── Subresource Filter
    │       ├── TpcdMetadata
    │       ├── TrustTokenKeyCommitments
    │       ├── Variations
    │       ├── WasmTtsEngine
    │       ├── WidevineCdm
    │       ├── ZxcvbnData
    │       ├── component_crx_cache
    │       ├── extensions_crx_cache
    │       ├── first_party_sets.db
    │       ├── first_party_sets.db-journal
    │       └── segmentation_platform
    ├── .wwebjs_auth_conn_1c68668c
    │   └── session
    │       ├── ActorSafetyLists
    │       ├── AmountExtractionHeuristicRegexes
    │       ├── CertificateRevocation
    │       ├── ChromeFeatureState
    │       ├── Crowd Deny
    │       ├── Default
    │       ├── DevToolsActivePort
    │       ├── FileTypePolicies
    │       ├── FirstPartySetsPreloaded
    │       ├── GrShaderCache
    │       ├── GraphiteDawnCache
    │       ├── HistorySearch
    │       ├── Last Version
    │       ├── Local State
    │       ├── MEIPreload
    │       ├── NativeMessagingHosts
    │       ├── OnDeviceHeadSuggestModel
    │       ├── OriginTrials
    │       ├── PKIMetadata
    │       ├── PlusAddressBlocklist
    │       ├── PrivacySandboxAttestationsPreloaded
    │       ├── RunningChromeVersion -> 145.0.7632.46:1
    │       ├── SSLErrorAssistant
    │       ├── Safe Browsing
    │       ├── SafetyTips
    │       ├── ShaderCache
    │       ├── SingletonCookie -> 17835331283689740668
    │       ├── SingletonLock -> Emre-MacBook-Pro.local-86965
    │       ├── SingletonSocket -> /var/folders/23/jrz_jjlj0t916n3sv1_xxmdr0000gn/T/com.google.chrome.for.testing.viOV5D/SingletonSocket
    │       ├── Subresource Filter
    │       ├── TpcdMetadata
    │       ├── TrustTokenKeyCommitments
    │       ├── Variations
    │       ├── WasmTtsEngine
    │       ├── WidevineCdm
    │       ├── ZxcvbnData
    │       ├── component_crx_cache
    │       ├── extensions_crx_cache
    │       ├── first_party_sets.db
    │       ├── first_party_sets.db-journal
    │       └── segmentation_platform
    ├── .wwebjs_auth_conn_3d5acf6b
    │   └── session
    │       ├── ActorSafetyLists
    │       ├── AmountExtractionHeuristicRegexes
    │       ├── CertificateRevocation
    │       ├── ChromeFeatureState
    │       ├── Crowd Deny
    │       ├── Default
    │       ├── DevToolsActivePort
    │       ├── FileTypePolicies
    │       ├── FirstPartySetsPreloaded
    │       ├── GrShaderCache
    │       ├── GraphiteDawnCache
    │       ├── HistorySearch
    │       ├── Last Version
    │       ├── Local State
    │       ├── MEIPreload
    │       ├── NativeMessagingHosts
    │       ├── OnDeviceHeadSuggestModel
    │       ├── OriginTrials
    │       ├── PKIMetadata
    │       ├── PlusAddressBlocklist
    │       ├── PrivacySandboxAttestationsPreloaded
    │       ├── RunningChromeVersion -> 145.0.7632.46:1
    │       ├── SSLErrorAssistant
    │       ├── Safe Browsing
    │       ├── SafetyTips
    │       ├── ShaderCache
    │       ├── SingletonCookie -> 16864010657526543738
    │       ├── SingletonLock -> Emre-MacBook-Pro.local-86790
    │       ├── SingletonSocket -> /var/folders/23/jrz_jjlj0t916n3sv1_xxmdr0000gn/T/com.google.chrome.for.testing.TIQxtE/SingletonSocket
    │       ├── Subresource Filter
    │       ├── TpcdMetadata
    │       ├── TrustTokenKeyCommitments
    │       ├── Variations
    │       ├── WasmTtsEngine
    │       ├── WidevineCdm
    │       ├── ZxcvbnData
    │       ├── component_crx_cache
    │       ├── extensions_crx_cache
    │       ├── first_party_sets.db
    │       ├── first_party_sets.db-journal
    │       └── segmentation_platform
    ├── .wwebjs_auth_conn_8ce1cf4d
    │   └── session
    │       ├── ActorSafetyLists
    │       ├── AmountExtractionHeuristicRegexes
    │       ├── BrowserMetrics-spare.pma
    │       ├── CertificateRevocation
    │       ├── ChromeFeatureState
    │       ├── Crowd Deny
    │       ├── Default
    │       ├── DevToolsActivePort
    │       ├── FileTypePolicies
    │       ├── FirstPartySetsPreloaded
    │       ├── GrShaderCache
    │       ├── GraphiteDawnCache
    │       ├── HistorySearch
    │       ├── Last Version
    │       ├── Local State
    │       ├── MEIPreload
    │       ├── NativeMessagingHosts
    │       ├── OnDeviceHeadSuggestModel
    │       ├── OriginTrials
    │       ├── PKIMetadata
    │       ├── PlusAddressBlocklist
    │       ├── PrivacySandboxAttestationsPreloaded
    │       ├── RunningChromeVersion -> 145.0.7632.46:1
    │       ├── SSLErrorAssistant
    │       ├── Safe Browsing
    │       ├── SafetyTips
    │       ├── ShaderCache
    │       ├── SingletonCookie -> 14245661862610055249
    │       ├── SingletonLock -> Emre-MacBook-Pro.local-86704
    │       ├── SingletonSocket -> /var/folders/23/jrz_jjlj0t916n3sv1_xxmdr0000gn/T/com.google.chrome.for.testing.n28iMY/SingletonSocket
    │       ├── Subresource Filter
    │       ├── TpcdMetadata
    │       ├── TrustTokenKeyCommitments
    │       ├── Variations
    │       ├── WasmTtsEngine
    │       ├── WidevineCdm
    │       ├── ZxcvbnData
    │       ├── component_crx_cache
    │       ├── extensions_crx_cache
    │       ├── first_party_sets.db
    │       ├── first_party_sets.db-journal
    │       └── segmentation_platform
    ├── .wwebjs_auth_conn_9167b222
    │   └── session
    │       ├── ActorSafetyLists
    │       ├── AmountExtractionHeuristicRegexes
    │       ├── CertificateRevocation
    │       ├── ChromeFeatureState
    │       ├── Crowd Deny
    │       ├── Default
    │       ├── DevToolsActivePort
    │       ├── FileTypePolicies
    │       ├── FirstPartySetsPreloaded
    │       ├── GrShaderCache
    │       ├── GraphiteDawnCache
    │       ├── HistorySearch
    │       ├── Last Version
    │       ├── Local State
    │       ├── MEIPreload
    │       ├── NativeMessagingHosts
    │       ├── OnDeviceHeadSuggestModel
    │       ├── OriginTrials
    │       ├── PKIMetadata
    │       ├── PlusAddressBlocklist
    │       ├── PrivacySandboxAttestationsPreloaded
    │       ├── RunningChromeVersion -> 145.0.7632.46:1
    │       ├── SSLErrorAssistant
    │       ├── Safe Browsing
    │       ├── SafetyTips
    │       ├── ShaderCache
    │       ├── SingletonCookie -> 2101153487178288387
    │       ├── SingletonLock -> Emre-MacBook-Pro.local-87169
    │       ├── SingletonSocket -> /var/folders/23/jrz_jjlj0t916n3sv1_xxmdr0000gn/T/com.google.chrome.for.testing.w2tVVg/SingletonSocket
    │       ├── Subresource Filter
    │       ├── TpcdMetadata
    │       ├── TrustTokenKeyCommitments
    │       ├── Variations
    │       ├── WasmTtsEngine
    │       ├── WidevineCdm
    │       ├── ZxcvbnData
    │       ├── component_crx_cache
    │       ├── extensions_crx_cache
    │       ├── first_party_sets.db
    │       ├── first_party_sets.db-journal
    │       └── segmentation_platform
    ├── .wwebjs_auth_conn_92b20111
    │   └── session
    │       ├── ActorSafetyLists
    │       ├── AmountExtractionHeuristicRegexes
    │       ├── BrowserMetrics-spare.pma
    │       ├── CertificateRevocation
    │       ├── ChromeFeatureState
    │       ├── Crowd Deny
    │       ├── Default
    │       ├── DevToolsActivePort
    │       ├── FileTypePolicies
    │       ├── FirstPartySetsPreloaded
    │       ├── GrShaderCache
    │       ├── GraphiteDawnCache
    │       ├── HistorySearch
    │       ├── Last Version
    │       ├── Local State
    │       ├── MEIPreload
    │       ├── NativeMessagingHosts
    │       ├── OnDeviceHeadSuggestModel
    │       ├── OriginTrials
    │       ├── PKIMetadata
    │       ├── PlusAddressBlocklist
    │       ├── PrivacySandboxAttestationsPreloaded
    │       ├── SSLErrorAssistant
    │       ├── Safe Browsing
    │       ├── SafetyTips
    │       ├── ShaderCache
    │       ├── Subresource Filter
    │       ├── TpcdMetadata
    │       ├── TrustTokenKeyCommitments
    │       ├── Variations
    │       ├── WasmTtsEngine
    │       ├── WidevineCdm
    │       ├── ZxcvbnData
    │       ├── component_crx_cache
    │       ├── extensions_crx_cache
    │       ├── first_party_sets.db
    │       ├── first_party_sets.db-journal
    │       └── segmentation_platform
    ├── .wwebjs_auth_conn_aa5b55e0
    │   └── session
    │       ├── ActorSafetyLists
    │       ├── AmountExtractionHeuristicRegexes
    │       ├── BrowserMetrics-spare.pma
    │       ├── CertificateRevocation
    │       ├── ChromeFeatureState
    │       ├── Crowd Deny
    │       ├── Default
    │       ├── DevToolsActivePort
    │       ├── FileTypePolicies
    │       ├── FirstPartySetsPreloaded
    │       ├── GrShaderCache
    │       ├── GraphiteDawnCache
    │       ├── HistorySearch
    │       ├── Last Version
    │       ├── Local State
    │       ├── MEIPreload
    │       ├── NativeMessagingHosts
    │       ├── OnDeviceHeadSuggestModel
    │       ├── OriginTrials
    │       ├── PKIMetadata
    │       ├── PlusAddressBlocklist
    │       ├── PrivacySandboxAttestationsPreloaded
    │       ├── SSLErrorAssistant
    │       ├── Safe Browsing
    │       ├── SafetyTips
    │       ├── ShaderCache
    │       ├── Subresource Filter
    │       ├── TpcdMetadata
    │       ├── TrustTokenKeyCommitments
    │       ├── Variations
    │       ├── WasmTtsEngine
    │       ├── WidevineCdm
    │       ├── ZxcvbnData
    │       ├── component_crx_cache
    │       ├── extensions_crx_cache
    │       ├── first_party_sets.db
    │       ├── first_party_sets.db-journal
    │       └── segmentation_platform
    ├── .wwebjs_auth_conn_bf3daef9
    │   └── session
    │       ├── ActorSafetyLists
    │       ├── AmountExtractionHeuristicRegexes
    │       ├── CertificateRevocation
    │       ├── ChromeFeatureState
    │       ├── Crowd Deny
    │       ├── Default
    │       ├── DevToolsActivePort
    │       ├── FileTypePolicies
    │       ├── FirstPartySetsPreloaded
    │       ├── GrShaderCache
    │       ├── GraphiteDawnCache
    │       ├── HistorySearch
    │       ├── Last Version
    │       ├── Local State
    │       ├── MEIPreload
    │       ├── NativeMessagingHosts
    │       ├── OnDeviceHeadSuggestModel
    │       ├── OriginTrials
    │       ├── PKIMetadata
    │       ├── PlusAddressBlocklist
    │       ├── PrivacySandboxAttestationsPreloaded
    │       ├── RunningChromeVersion -> 145.0.7632.46:1
    │       ├── SSLErrorAssistant
    │       ├── Safe Browsing
    │       ├── SafetyTips
    │       ├── ShaderCache
    │       ├── SingletonCookie -> 12316542492002759462
    │       ├── SingletonLock -> Emre-MacBook-Pro.local-86362
    │       ├── SingletonSocket -> /var/folders/23/jrz_jjlj0t916n3sv1_xxmdr0000gn/T/com.google.chrome.for.testing.BMvrkD/SingletonSocket
    │       ├── Subresource Filter
    │       ├── TpcdMetadata
    │       ├── TrustTokenKeyCommitments
    │       ├── Variations
    │       ├── WasmTtsEngine
    │       ├── WidevineCdm
    │       ├── ZxcvbnData
    │       ├── component_crx_cache
    │       ├── extensions_crx_cache
    │       ├── first_party_sets.db
    │       ├── first_party_sets.db-journal
    │       └── segmentation_platform
    ├── Dockerfile
    ├── asistan_start.log
    ├── index-multi.js
    ├── index.js
    ├── package-lock.json
    ├── package.json
    └── stop-bridge.sh

403 directories, 551 files

```

---

## 📌 Kullanım Talimatları (AI İçin)

Bu dosya, kod üretmeden önce projenin mevcut yapısını kontrol etmek içindir:

1. **Yeni dosya oluşturmadan önce:** Bu ağaçta benzer bir dosya var mı kontrol et
2. **Yeni klasör oluşturmadan önce:** Mevcut klasör yapısına uygun mu kontrol et
3. **Import/require yapmadan önce:** Dosya yolu doğru mu kontrol et
4. **Kod kopyalamadan önce:** Aynı fonksiyon başka dosyada var mı kontrol et

**Örnek:**
- ❌ "Yeni bir auth.py oluşturalım" → ✅ Kontrol et, zaten `app/auth.py` var mı?
- ❌ "config/ klasörü oluşturalım" → ✅ Kontrol et, zaten `config/` var mı?
- ❌ `from utils import helper` → ✅ Kontrol et, `utils/helper.py` gerçekten var mı?

---

**Not:** Bu dosya otomatik oluşturulmuştur. Proje yapısı değiştikçe güncellenmelidir.

```bash
# Güncelleme komutu
python3 /Users/emre/Desktop/Emare/create_dosya_yapisi.py
```
