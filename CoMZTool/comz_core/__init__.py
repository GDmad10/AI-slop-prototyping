"""CoMZ preservation core — lawful analysis only, no DRM circumvention."""
from .identify import identify_file, is_likely_comz
from .analyze import analyze_file, structural_map
from .catalog import Catalog
from .compare import compare_files
from .unity import scan_unity
from .wrappers import detect_wrapper
from . import rg_adguard
from . import dbox
from . import wpcompat

__all__ = [
    "identify_file",
    "is_likely_comz",
    "analyze_file",
    "structural_map",
    "Catalog",
    "compare_files",
    "scan_unity",
    "detect_wrapper",
    "rg_adguard",
    "dbox",
    "wpcompat",
]
