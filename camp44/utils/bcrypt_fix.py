"""
Fix for bcrypt module compatibility with passlib.

Modern versions of bcrypt no longer include the __about__ attribute
that passlib looks for to determine version information.

This module patches bcrypt to provide the missing attribute and
prevent the AttributeError when passlib tries to access it.
"""
import bcrypt

# Check if bcrypt lacks the __about__ attribute
if not hasattr(bcrypt, '__about__'):
    # Add a minimal __about__ module with version attribute
    class AboutModule:
        __version__ = getattr(bcrypt, '__version__', '4.0.0')  # Use actual version if available, or fallback
    
    bcrypt.__about__ = AboutModule()

# Function to apply the patch
def apply_bcrypt_patch():
    """Apply the bcrypt patch to fix passlib compatibility."""
    # Already applied in the module import
    pass
