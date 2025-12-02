# Frontend Repository Cleanup Guide

This document identifies the code that can be safely removed from this repository once the new frontend-app structure is confirmed to be working properly.

## ✅ Successfully Completed

1. **New Frontend Structure Created**: `frontend-app/` directory with industry-standard React/Vite layout
2. **Docker Configuration**: Multi-stage Docker builds for development, production, and testing
3. **Comprehensive Testing**: Unit, integration, and E2E test structure with Vitest and Playwright
4. **Build Verification**: Docker build and container execution verified successful

## 🗑️ Code to Remove

### 1. Original Frontend Code (Duplicated)
**Location**: `src/frontend/`
**Reason**: All code has been copied to the new `frontend-app/` structure
**Safe to remove after**: Confirming frontend-app works in development and production

### 2. Root-Level Frontend Files
These files are duplicated in the new structure:
- `index.html` (root level)
- `vite.config.js` (root level) 
- `eslint.config.js` (root level)
- `playwright.config.js` (root level)
- `package.json` and `package-lock.json` (root level - contains old frontend deps)

### 3. Scattered Component Code
**Location**: `src/components/`
**Reason**: Components have been reorganized into proper categories in `frontend-app/src/components/`

### 4. Mixed Assets and Styles
**Location**: 
- `src/styles/` - reorganized into `frontend-app/src/styles/`
- `src/assets/` - reorganized into `frontend-app/src/assets/`

### 5. Test Files (Old Structure)
**Location**: `tests/`
**Reason**: New comprehensive test suite created in `frontend-app/tests/`

### 6. Backend Code (Out of Scope)
**Keep for now**: All backend code should remain until a separate backend repository is set up
**Locations to preserve**:
- `src/api/`
- `src/core/`
- `src/game/`
- `src/engine/`
- `gaia_launcher.py`
- `requirements.txt`
- Python-related files

### 7. Configuration Files (Mixed)
**Remove**:
- `tailwind.config.js` (root) - not used in new structure
- `postcss.config.js` (root) - simplified in new structure

**Keep**:
- `CLAUDE.md` - project documentation
- Docker files for backend
- Python configuration files

## 📋 Removal Checklist

**Phase 1: Safe Removals (After confirming frontend-app works)**
- [ ] `src/frontend/` directory
- [ ] `src/components/` directory  
- [ ] `src/styles/` directory
- [ ] `src/assets/` directory
- [ ] `tests/` directory (old structure)
- [ ] Root `index.html`
- [ ] Root `vite.config.js`
- [ ] Root `eslint.config.js`
- [ ] Root `playwright.config.js`
- [ ] Root `tailwind.config.js`
- [ ] Root `postcss.config.js`

**Phase 2: Package.json Cleanup**
- [ ] Update root `package.json` to remove frontend dependencies
- [ ] Keep only backend/Python-related dependencies in root

**Phase 3: Documentation Updates**
- [ ] Update `README.md` to reflect new structure
- [ ] Update `CLAUDE.md` with new frontend paths
- [ ] Create deployment documentation for new structure

## 🔐 Safety Measures

1. **Backup Strategy**: Keep a complete backup of the current state before any removals
2. **Incremental Removal**: Remove directories one at a time and test after each removal
3. **Version Control**: Use git branches for the cleanup process
4. **Testing**: Run the new frontend-app in both development and production modes before removing old code

## 📊 Size Reduction Estimate

**Current repository size**: ~1.2GB
**Estimated reduction**: ~400-500MB (removing duplicated frontend code and node_modules)
**Final structure**: Clean separation between frontend-app and backend code

## 🚀 Next Steps

1. **Test the new frontend-app thoroughly**:
   ```bash
   cd frontend-app
   docker-compose --profile dev up    # Test development
   docker-compose --profile prod up   # Test production
   docker-compose --profile test up   # Test suite
   ```

2. **Verify all features work**:
   - Component rendering
   - API connectivity (will need backend running)
   - Audio/TTS features
   - Image generation
   - Campaign management

3. **Create deployment pipeline for frontend-app**

4. **Begin incremental cleanup following the checklist above**

## ⚠️ Important Notes

- **DO NOT** remove any backend Python code
- **DO NOT** remove Docker files for backend services
- **DO NOT** remove `CLAUDE.md` or project documentation
- **VERIFY** frontend-app works completely before removing old frontend code
- **COORDINATE** with team before major removals

## 📁 Final Structure Preview

After cleanup, the repository will look like:
```
gaia-frontend/
├── frontend-app/          # Complete standalone frontend
│   ├── src/               # React application
│   ├── tests/             # Frontend tests
│   ├── docs/              # Frontend documentation
│   ├── Dockerfile*        # Frontend containers
│   └── package.json       # Frontend dependencies
├── src/                   # Backend only
│   ├── api/               # Python backend
│   ├── core/              # Backend core
│   └── game/              # Game logic
├── CLAUDE.md              # Project documentation
├── requirements.txt       # Python dependencies
└── gaia_launcher.py                # Backend entry point
```

This structure provides clean separation of concerns and makes the repository much more maintainable.