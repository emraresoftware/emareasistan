# 🔥 Kıvılcım Raporu

> Oluşturulma: 2026-02-28 03:13

## 📝 TODO / FIXME (1 adet)

| Dosya | Satır | Tür | Not |
|-------|-------|-----|-----|
| `scripts/kivilcim.py` | 211 | TODO | /FIXME |

## 🔐 Hardcoded Secret Şüphelileri (0 adet)

Bulunamadı ✅

## 🌐 API Endpoint'leri (241 adet)

| Method | Path | Fonksiyon | Dosya |
|--------|------|-----------|-------|
| GET | `/` | admin_index | `admin/routes_auth.py` |
| GET | `/` | root | `main.py` |
| POST | `/abandoned-cart` | cron_abandoned_cart | `integrations/cron_api.py` |
| GET | `/admin-staff/invoices` | admin_staff_invoices | `admin/routes.py` |
| POST | `/admin-staff/invoices/save` | admin_staff_invoice_save | `admin/routes.py` |
| POST | `/admin-staff/invoices/{id}/status` | admin_staff_invoice_status | `admin/routes.py` |
| GET | `/admin-staff/leaves` | admin_staff_leaves | `admin/routes.py` |
| POST | `/admin-staff/leaves/save` | admin_staff_leave_save | `admin/routes.py` |
| POST | `/admin-staff/leaves/{id}/status` | admin_staff_leave_status | `admin/routes.py` |
| GET | `/admin-staff/purchase-orders` | admin_staff_purchase_orders | `admin/routes.py` |
| POST | `/admin-staff/purchase-orders/save` | admin_staff_purchase_order_save | `admin/routes.py` |
| POST | `/admin-staff/purchase-orders/{id}/status` | admin_staff_purchase_order_status | `admin/routes.py` |
| GET | `/agent` | agent_panel | `admin/routes_agent.py` |
| GET | `/agent/chat/{id}` | agent_chat | `admin/routes_agent.py` |
| POST | `/agent/set-profile` | agent_set_profile | `admin/routes_agent.py` |
| GET | `/albums` | albums_list | `admin/routes.py` |
| GET | `/albums/new` | album_new | `admin/routes.py` |
| POST | `/albums/save` | album_save | `admin/routes.py` |
| POST | `/albums/upload` | album_upload | `admin/routes.py` |
| GET | `/albums/{id}` | album_edit | `admin/routes.py` |
| POST | `/albums/{id}/delete` | album_delete | `admin/routes.py` |
| GET | `/amazon` | _redirect_marketplace_placeholder | `admin/routes.py` |
| GET | `/amazon/orders` | _redirect_marketplace_placeholder | `admin/routes.py` |
| GET | `/amazon/settings` | _redirect_marketplace_placeholder | `admin/routes.py` |
| GET | `/analytics` | analytics_page | `admin/routes_dashboard.py` |
| POST | `/analytics/local-threshold/apply` | analytics_apply_local_threshold | `admin/routes_dashboard.py` |
| GET | `/api/agent/albums` | api_agent_albums | `admin/routes_agent.py` |
| GET | `/api/agent/contacts` | api_agent_contacts | `admin/routes_agent.py` |
| POST | `/api/agent/conversation-notes/{conv_id}` | api_agent_conversation_notes | `admin/routes_agent.py` |
| GET | `/api/agent/conversations` | api_agent_conversations | `admin/routes_agent.py` |
| POST | `/api/agent/followup/{conv_id}` | api_agent_create_followup | `admin/routes_agent.py` |
| GET | `/api/agent/insights/{conv_id}` | api_agent_insights | `admin/routes_agent.py` |
| GET | `/api/agent/messages/{conv_id}` | api_agent_messages | `admin/routes_agent.py` |
| POST | `/api/agent/release/{conv_id}` | api_agent_release | `admin/routes_agent.py` |
| POST | `/api/agent/send-image` | api_agent_send_image | `admin/routes_agent.py` |
| POST | `/api/agent/send-message` | api_agent_send_message | `admin/routes_agent.py` |
| POST | `/api/agent/start-chat` | api_agent_start_chat | `admin/routes_agent.py` |
| POST | `/api/agent/takeover/{conv_id}` | api_agent_takeover | `admin/routes_agent.py` |
| GET | `/api/ai-status` | api_ai_status | `admin/routes_settings.py` |
| GET | `/api/album-images` | api_album_images | `admin/routes.py` |
| GET | `/api/analytics` | api_analytics | `admin/routes_dashboard.py` |
| POST | `/api/chat/support` | support_chat_send | `integrations/support_chat_api.py` |
| GET | `/api/chat/support/health` | support_chat_health | `integrations/support_chat_api.py` |
| POST | `/api/chat/web` | web_chat_send | `integrations/web_chat_api.py` |
| GET | `/api/debug-session` | api_debug_session | `admin/routes_agent.py` |
| GET | `/api/new-orders-count` | api_new_orders_count | `admin/routes_dashboard.py` |
| GET | `/api/products` | api_products | `admin/routes.py` |
| GET | `/api/quick-replies` | api_quick_replies | `admin/routes_agent.py` |
| POST | `/api/register/analyze` | api_register_analyze | `admin/routes_auth.py` |
| GET | `/api/reminders/pending` | api_reminders_pending | `admin/routes.py` |
| GET | `/api/vehicle-models` | api_vehicle_models | `admin/routes.py` |
| GET | `/api/whatsapp-status` | api_whatsapp_status | `admin/routes_agent.py` |
| GET | `/appointments` | appointments_list | `admin/routes.py` |
| POST | `/appointments/settings` | appointments_settings_save | `admin/routes.py` |
| POST | `/appointments/{id}/cancel` | appointment_cancel | `admin/routes.py` |
| POST | `/appointments/{id}/complete` | appointment_complete | `admin/routes.py` |
| GET | `/aras` |  | `admin/routes.py` |
| GET | `/aras/settings` |  | `admin/routes.py` |
| GET | `/cargo` | cargo_list | `admin/routes_orders.py` |
| GET | `/cargo/{company}` | cargo_list | `admin/routes_orders.py` |
| GET | `/chat-audits` | chat_audits_list | `admin/routes_rules_workflows.py` |
| POST | `/chat-audits/toggle` | chat_audits_toggle | `admin/routes_rules_workflows.py` |
| GET | `/chat/{tenant_slug}` | web_chat_page | `integrations/web_chat_api.py` |
| GET | `/connections` | get_bridge_connections | `integrations/bridge_api.py` |
| GET | `/contacts` | contacts_list | `admin/routes.py` |
| POST | `/contacts/save` | contacts_save | `admin/routes.py` |
| POST | `/contacts/{id}/delete` | contacts_delete | `admin/routes.py` |
| GET | `/conversations` | conversations_list | `admin/routes.py` |
| POST | `/conversations/clear` | conversations_clear | `admin/routes.py` |
| GET | `/conversations/export` | conversations_export | `admin/routes.py` |
| GET | `/conversations/{id}` | conversation_detail | `admin/routes.py` |
| POST | `/conversations/{id}/delete` | conversation_delete | `admin/routes.py` |
| POST | `/daily-digest` | cron_daily_digest | `integrations/cron_api.py` |
| GET | `/dashboard` | dashboard | `admin/routes_dashboard.py` |
| GET | `/dhl` | _redirect_cargo_placeholder | `admin/routes.py` |
| GET | `/diagnose` | diagnose | `integrations/whatsapp_qr.py` |
| GET | `/export-templates` | export_templates_list | `admin/routes.py` |
| GET | `/export-templates/new` | export_template_new | `admin/routes.py` |
| POST | `/export-templates/save` | export_template_save | `admin/routes.py` |
| GET | `/export-templates/{id}` | export_template_edit | `admin/routes.py` |
| POST | `/export-templates/{id}/delete` | export_template_delete | `admin/routes.py` |
| GET | `/export-templates/{id}/export` | export_template_manual_export | `admin/routes.py` |
| GET | `/facebook` |  | `admin/routes.py` |
| GET | `/facebook/messages` |  | `admin/routes.py` |
| GET | `/facebook/settings` |  | `admin/routes.py` |
| POST | `/feedback` | message_feedback_post | `admin/routes.py` |
| GET | `/health` | health | `main.py` |
| GET | `/hepsiburada` |  | `admin/routes.py` |
| GET | `/hepsiburada/orders` | _redirect_marketplace_placeholder | `admin/routes.py` |
| GET | `/hepsiburada/settings` | _redirect_marketplace_placeholder | `admin/routes.py` |
| GET | `/instagram` | instagram_dashboard | `admin/routes.py` |
| GET | `/instagram/settings` | _redirect_instagram_settings | `admin/routes.py` |
| GET | `/instagram/setup` | instagram_setup | `admin/routes.py` |
| GET | `/linkedin` | _redirect_social_placeholder | `admin/routes.py` |
| POST | `/login` | admin_login | `admin/routes_auth.py` |
| GET | `/login/choose-partner` | login_choose_partner | `admin/routes_auth.py` |
| POST | `/login/complete-partner` | login_complete_partner | `admin/routes_auth.py` |
| GET | `/logout` | admin_logout | `admin/routes_auth.py` |
| GET | `/mng` | _redirect_cargo_placeholder | `admin/routes.py` |
| GET | `/mng/settings` | _redirect_cargo_placeholder | `admin/routes.py` |
| GET | `/orders` | orders_list | `admin/routes_orders.py` |
| GET | `/orders/export` | orders_export | `admin/routes_orders.py` |
| GET | `/orders/{id}` | order_detail | `admin/routes_orders.py` |
| POST | `/orders/{id}/update-cargo` | order_update_cargo | `admin/routes_orders.py` |
| POST | `/orders/{id}/update-notes` | order_update_notes | `admin/routes_orders.py` |
| POST | `/orders/{id}/update-status` | order_update_status | `admin/routes_orders.py` |
| GET | `/p/{partner_slug}` | admin_login_partner | `admin/routes_auth.py` |
| GET | `/partner` | partner_admin_page | `admin/routes_partner_super.py` |
| GET | `/partner/deploy` | partner_deploy_form | `admin/partner.py` |
| POST | `/partner/deploy` | partner_deploy_submit | `admin/partner.py` |
| GET | `/partner/deploy/log/{tenant_slug}` | partner_deploy_log | `admin/partner.py` |
| GET | `/partner/deploy/status/{tenant_slug}` | partner_deploy_status | `admin/partner.py` |
| POST | `/partner/enter/{id}` | partner_admin_enter | `admin/routes_partner_super.py` |
| GET | `/partner/modules/{tid}` | partner_admin_modules | `admin/routes_partner_super.py` |
| POST | `/partner/modules/{tid}` | partner_admin_modules_save | `admin/routes_partner_super.py` |
| GET | `/partner/panel` | partner_admin_panel | `admin/routes_partner_super.py` |
| GET | `/partner/servers` | partner_servers | `admin/partner.py` |
| GET | `/partner/settings/branding` | partner_branding_page | `admin/routes_partner_super.py` |
| POST | `/partner/settings/branding` | partner_branding_save | `admin/routes_partner_super.py` |
| GET | `/partner/tenant/{tid}/branding` | partner_tenant_branding_page | `admin/routes_partner_super.py` |
| POST | `/partner/tenant/{tid}/branding` | partner_tenant_branding_save | `admin/routes_partner_super.py` |
| POST | `/partner/tenants` | partner_admin_create_tenant | `admin/routes_partner_super.py` |
| POST | `/partner/tenants/{tid}/delete` | partner_admin_delete_tenant | `admin/routes_partner_super.py` |
| GET | `/partner/users` | partner_admin_users | `admin/routes_partner_super.py` |
| GET | `/payment` | _redirect_payment | `admin/routes.py` |
| GET | `/payment/links` | _redirect_payment | `admin/routes.py` |
| GET | `/payment/settings` | _redirect_payment | `admin/routes.py` |
| GET | `/paypal` | _redirect_payment_placeholder | `admin/routes.py` |
| GET | `/paypal/settings` | _redirect_payment_placeholder | `admin/routes.py` |
| POST | `/proactive` | cron_proactive_messages | `integrations/cron_api.py` |
| POST | `/process` | process_message | `integrations/whatsapp_qr.py` |
| GET | `/process-config` | process_config_list | `admin/routes_rules_workflows.py` |
| GET | `/process-config/edit` | process_config_edit | `admin/routes_rules_workflows.py` |
| POST | `/process-config/save` | process_config_save | `admin/routes_rules_workflows.py` |
| GET | `/products` | products_list | `admin/routes.py` |
| GET | `/products/gallery` | products_gallery | `admin/routes.py` |
| POST | `/products/import-to-db` | products_import_to_db | `admin/routes.py` |
| GET | `/products/new` | product_new | `admin/routes.py` |
| POST | `/products/save` | product_save | `admin/routes.py` |
| GET | `/products/{id}` | product_edit | `admin/routes.py` |
| POST | `/products/{id}/delete` | product_delete | `admin/routes.py` |
| GET | `/ptt` | _redirect_cargo_placeholder | `admin/routes.py` |
| GET | `/quick-replies` | quick_replies_list | `admin/routes_agent.py` |
| POST | `/quick-replies/save` | quick_replies_save | `admin/routes_agent.py` |
| POST | `/quick-replies/{id}/delete` | quick_replies_delete | `admin/routes_agent.py` |
| GET | `/register` | register_page | `admin/routes_auth.py` |
| POST | `/register` | register_submit | `admin/routes_auth.py` |
| GET | `/register/confirm` | register_confirm | `admin/routes_auth.py` |
| GET | `/register/sent` | register_sent | `admin/routes_auth.py` |
| GET | `/reminders` | reminders_list | `admin/routes.py` |
| GET | `/reminders/new` | reminder_new | `admin/routes.py` |
| POST | `/reminders/save` | reminder_save | `admin/routes.py` |
| GET | `/reminders/{id}` | reminder_edit | `admin/routes.py` |
| POST | `/reminders/{id}/complete` | reminder_complete | `admin/routes.py` |
| POST | `/reminders/{id}/delete` | reminder_delete | `admin/routes.py` |
| GET | `/rules` | rules_list | `admin/routes_rules_workflows.py` |
| GET | `/rules/new` | rule_new | `admin/routes_rules_workflows.py` |
| POST | `/rules/save` | rule_save | `admin/routes_rules_workflows.py` |
| GET | `/rules/{id}` | rule_edit | `admin/routes_rules_workflows.py` |
| POST | `/rules/{id}/delete` | rule_delete | `admin/routes_rules_workflows.py` |
| GET | `/settings` | settings_index | `admin/routes_settings.py` |
| GET | `/settings/account` | settings_account | `admin/routes_settings.py` |
| POST | `/settings/account` | settings_account_save | `admin/routes_settings.py` |
| GET | `/settings/ai` | settings_ai | `admin/routes_settings.py` |
| POST | `/settings/ai` | settings_ai_save | `admin/routes_settings.py` |
| GET | `/settings/api` | settings_api | `admin/routes_settings.py` |
| POST | `/settings/api` | settings_api_save | `admin/routes_settings.py` |
| POST | `/settings/api/preview/{module_id}` | settings_api_preview_pull | `admin/routes_settings.py` |
| POST | `/settings/api/push/{module_id}` | settings_api_sync_push | `admin/routes_settings.py` |
| POST | `/settings/api/sync/{module_id}` | settings_api_sync_pull | `admin/routes_settings.py` |
| POST | `/settings/api/test-url` | settings_api_test_url | `admin/routes_settings.py` |
| GET | `/settings/branding` | settings_branding | `admin/routes_settings.py` |
| POST | `/settings/branding` | settings_branding_save | `admin/routes_settings.py` |
| GET | `/settings/web-chat` | settings_web_chat | `admin/routes_settings.py` |
| GET | `/stripe` | _redirect_payment_placeholder | `admin/routes.py` |
| GET | `/stripe/settings` | _redirect_payment_placeholder | `admin/routes.py` |
| GET | `/super` | super_admin_page | `admin/routes_partner_super.py` |
| POST | `/super/enter/{id}` | super_admin_enter | `admin/routes_partner_super.py` |
| GET | `/super/login-logs` | super_admin_login_logs | `admin/routes_partner_super.py` |
| GET | `/super/modules/{id}` | super_admin_modules | `admin/routes_partner_super.py` |
| POST | `/super/modules/{id}` | super_admin_modules_save | `admin/routes_partner_super.py` |
| POST | `/super/partners` | super_admin_create_partner | `admin/routes_partner_super.py` |
| POST | `/super/partners/{pid}/admin-user` | super_admin_create_partner_admin | `admin/routes_partner_super.py` |
| POST | `/super/partners/{pid}/delete` | super_admin_delete_partner | `admin/routes_partner_super.py` |
| POST | `/super/tenants/{tid}/delete` | super_admin_delete_tenant | `admin/routes_partner_super.py` |
| POST | `/super/tenants/{tid}/partner` | super_admin_assign_tenant_partner | `admin/routes_partner_super.py` |
| GET | `/super/user-status` | super_admin_user_status | `admin/routes_partner_super.py` |
| GET | `/t/{tenant_slug}` | admin_login_tenant | `admin/routes_auth.py` |
| GET | `/telegram` | _redirect_telegram | `admin/routes.py` |
| GET | `/telegram/bot` | _redirect_telegram_settings | `admin/routes.py` |
| GET | `/telegram/settings` | _redirect_telegram_settings | `admin/routes.py` |
| GET | `/test` | test | `integrations/whatsapp_qr.py` |
| GET | `/tiktok` | _redirect_social_placeholder | `admin/routes.py` |
| GET | `/training` | training_list | `admin/routes_rules_workflows.py` |
| POST | `/training/from-chat` | training_from_chat | `admin/routes_rules_workflows.py` |
| GET | `/training/import` | training_import_get | `admin/routes_rules_workflows.py` |
| POST | `/training/import` | training_import_post | `admin/routes_rules_workflows.py` |
| GET | `/training/new` | training_new | `admin/routes_rules_workflows.py` |
| POST | `/training/quick-reply-options/save` | training_quick_reply_options_save | `admin/routes_rules_workflows.py` |
| POST | `/training/response-rules/save` | training_response_rules_save | `admin/routes_rules_workflows.py` |
| POST | `/training/save` | training_save | `admin/routes_rules_workflows.py` |
| POST | `/training/sync-embeddings` | training_sync_embeddings | `admin/routes_rules_workflows.py` |
| POST | `/training/welcome-scenarios/preview` | training_welcome_scenarios_preview | `admin/routes_rules_workflows.py` |
| POST | `/training/welcome-scenarios/save` | training_welcome_scenarios_save | `admin/routes_rules_workflows.py` |
| GET | `/training/{id}` | training_edit | `admin/routes_rules_workflows.py` |
| POST | `/training/{id}/delete` | training_delete | `admin/routes_rules_workflows.py` |
| GET | `/trendyol` |  | `admin/routes.py` |
| GET | `/trendyol/orders` |  | `admin/routes.py` |
| GET | `/trendyol/settings` |  | `admin/routes.py` |
| GET | `/twitter` | _redirect_social_placeholder | `admin/routes.py` |
| GET | `/twitter/dm` | _redirect_social_placeholder | `admin/routes.py` |
| GET | `/twitter/settings` | _redirect_social_placeholder | `admin/routes.py` |
| GET | `/ups` | _redirect_cargo_placeholder | `admin/routes.py` |
| GET | `/users` | users_list | `admin/routes.py` |
| POST | `/users/save` | users_save | `admin/routes.py` |
| POST | `/users/{id}/delete` | users_delete | `admin/routes.py` |
| GET | `/videos` | videos_list | `admin/routes.py` |
| GET | `/videos/new` | video_new | `admin/routes.py` |
| POST | `/videos/save` | video_save | `admin/routes.py` |
| POST | `/videos/upload` | video_upload | `admin/routes.py` |
| GET | `/videos/{id}` | video_edit | `admin/routes.py` |
| POST | `/videos/{id}/delete` | video_delete | `admin/routes.py` |
| GET | `/whatsapp` | whatsapp_list | `admin/routes.py` |
| GET | `/whatsapp/connection` | _redirect_whatsapp_connection | `admin/routes.py` |
| POST | `/whatsapp/create` | whatsapp_create | `admin/routes.py` |
| GET | `/whatsapp/qr/{conn_id}` | whatsapp_qr_proxy | `admin/routes.py` |
| GET | `/whatsapp/settings` | _redirect_whatsapp_settings | `admin/routes.py` |
| POST | `/whatsapp/{id}/delete` | whatsapp_delete | `admin/routes.py` |
| GET | `/workflows` | workflows_list | `admin/routes_rules_workflows.py` |
| GET | `/workflows/new` | workflow_new | `admin/routes_rules_workflows.py` |
| POST | `/workflows/save` | workflow_save | `admin/routes_rules_workflows.py` |
| POST | `/workflows/steps/{step_id}/delete` | workflow_step_delete | `admin/routes_rules_workflows.py` |
| POST | `/workflows/steps/{step_id}/update` | workflow_step_update | `admin/routes_rules_workflows.py` |
| GET | `/workflows/{id}` | workflow_edit | `admin/routes_rules_workflows.py` |
| GET | `/workflows/{id}/builder` | workflow_builder | `admin/routes_rules_workflows.py` |
| POST | `/workflows/{id}/delete` | workflow_delete | `admin/routes_rules_workflows.py` |
| GET | `/workflows/{id}/graph` | workflow_graph_api | `admin/routes_rules_workflows.py` |
| POST | `/workflows/{id}/graph` | workflow_graph_save | `admin/routes_rules_workflows.py` |
| POST | `/workflows/{id}/steps/add` | workflow_step_add | `admin/routes_rules_workflows.py` |
| GET | `/yurtici` |  | `admin/routes.py` |
| GET | `/yurtici/settings` |  | `admin/routes.py` |

## ⚙️ Env Değişkenleri (1 adet)

| Değişken |
|----------|
| `REPAIR_PASSWORD` |

## 📖 Docstring Eksikleri (82 adet)

| Dosya | Satır | Tür | İsim |
|-------|-------|-----|------|
| `admin/routes_agent.py` | 157 | def | `norm_phone` |
| `integrations/channels/base.py` | 35 | def | `from_dict` |
| `integrations/channels/instagram_channel.py` | 21 | def | `platform_id` |
| `integrations/channels/instagram_channel.py` | 29 | def | `send_text` |
| `integrations/channels/instagram_channel.py` | 45 | def | `send_image` |
| `integrations/channels/telegram_channel.py` | 20 | def | `__init__` |
| `integrations/channels/telegram_channel.py` | 26 | def | `platform_id` |
| `integrations/channels/telegram_channel.py` | 37 | def | `send_text` |
| `integrations/channels/telegram_channel.py` | 46 | def | `send_image` |
| `integrations/channels/telegram_channel.py` | 55 | def | `send_location` |
| `integrations/channels/whatsapp_cloud.py` | 15 | def | `platform_id` |
| `integrations/channels/whatsapp_cloud.py` | 22 | def | `send_text` |
| `integrations/channels/whatsapp_cloud.py` | 40 | def | `send_image` |
| `integrations/channels/whatsapp_cloud.py` | 55 | def | `send_location` |
| `integrations/chat_handler.py` | 38 | def | `__init__` |
| `integrations/handlers/appointment_handler.py` | 12 | def | `__init__` |
| `integrations/handlers/cargo_handler.py` | 7 | def | `__init__` |
| `integrations/handlers/order_handler.py` | 13 | def | `__init__` |
| `integrations/handlers/product_handler.py` | 12 | def | `__init__` |
| `integrations/support_chat_api.py` | 97 | class | `SupportChatRequest` |
| `integrations/web_chat_api.py` | 30 | class | `WebChatRequest` |
| `integrations/whatsapp_qr.py` | 33 | class | `ProcessRequest` |
| `models/order.py` | 10 | class | `OrderStatus` |
| `run.py` | 25 | def | `cleanup` |
| `scraper/meridyen_scraper.py` | 60 | def | `__init__` |
| `scripts/add_docstrings.py` | 213 | def | `main` |
| `scripts/assign_tenant_to_partner.py` | 12 | def | `main` |
| `scripts/check_defence360.py` | 8 | def | `main` |
| `scripts/check_support_chat_create_rule.py` | 64 | def | `main` |
| `scripts/check_whatsapp.py` | 14 | def | `main` |
| `scripts/create_piramit_vpn_workflow.py` | 70 | def | `main` |
| `scripts/create_sample_album.py` | 24 | def | `main` |
| `scripts/enable_web_chat_tenant.py` | 10 | def | `main` |
| `scripts/export_tenant6_training.py` | 61 | def | `main` |
| `scripts/fix_tenant_check.py` | 21 | def | `main` |
| `scripts/fix_whatsapp.py` | 15 | def | `main` |
| `scripts/import_tenant6_training.py` | 73 | def | `main` |
| `scripts/list_tenants_partners.py` | 7 | def | `main` |
| `scripts/load_tenant6_quick_replies.py` | 31 | def | `main` |
| `scripts/load_tenant6_rules.py` | 29 | def | `main` |
| `scripts/local_llm/chat.py` | 8 | def | `pick_device` |
| `scripts/local_llm/chat.py` | 16 | def | `main` |
| `scripts/local_llm/extract_training_data.py` | 20 | class | `Pair` |
| `scripts/local_llm/extract_training_data.py` | 76 | def | `extract_pairs` |
| `scripts/local_llm/extract_training_data.py` | 131 | def | `main_async` |
| `scripts/local_llm/prepare_dataset.py` | 6 | def | `format_record` |
| `scripts/local_llm/prepare_dataset.py` | 14 | def | `main` |
| `scripts/local_llm/train_lora.py` | 16 | def | `pick_device` |
| `scripts/local_llm/train_lora.py` | 25 | class | `Config` |
| `scripts/local_llm/train_lora.py` | 36 | def | `parse_args` |

... ve 32 adet daha

## 🛡️ Auth Kontrolü Şüpheli Endpoint'ler (0 adet)

Bulunamadı ✅
