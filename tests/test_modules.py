"""
Modül sistemi testleri.
"""
import pytest


class TestModules:
    """services/modules.py testleri."""

    def test_all_modules_exists(self):
        """AVAILABLE_MODULES listesi tanımlı."""
        from services.modules import AVAILABLE_MODULES
        assert isinstance(AVAILABLE_MODULES, list)

    def test_modules_count(self):
        """En az 50 modül var."""
        from services.modules import AVAILABLE_MODULES
        assert len(AVAILABLE_MODULES) >= 50

    def test_module_structure(self):
        """Her modülde id, name, category alanları var."""
        from services.modules import AVAILABLE_MODULES
        for mod in AVAILABLE_MODULES:
            assert "id" in mod, f"Modülde id eksik: {mod}"
            assert "name" in mod, f"Modülde name eksik: {mod}"
            assert "category" in mod, f"Modülde category eksik: {mod}"

    def test_module_ids_unique(self):
        """Modül ID'leri benzersiz."""
        from services.modules import AVAILABLE_MODULES
        ids = [m["id"] for m in AVAILABLE_MODULES]
        assert len(ids) == len(set(ids)), f"Mükerrer modül ID'leri: {[x for x in ids if ids.count(x) > 1]}"

    def test_core_modules_exist(self):
        """Temel modüller mevcut."""
        from services.modules import AVAILABLE_MODULES
        ids = {m["id"] for m in AVAILABLE_MODULES}
        core = {"whatsapp", "products", "orders", "analytics", "training"}
        missing = core - ids
        assert not missing, f"Eksik temel modüller: {missing}"

    def test_module_categories(self):
        """Modül kategorileri dolu."""
        from services.modules import AVAILABLE_MODULES
        for mod in AVAILABLE_MODULES:
            assert mod["category"], f"Modül {mod['id']} kategorisi boş"
