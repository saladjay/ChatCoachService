# Legacy Prompts Archive

This folder contains historical prompt versions that are no longer actively used in the system but are preserved for reference and comparison purposes.

## Current System (Phase 3)

The current system uses:
- **Compact prompts** defined in `app/services/prompt_compact.py`
- **Dynamic assembly** via `app/services/prompt_assembler.py`
- **Version tracking** with `[PROMPT:version_id]` identifiers

## Archived Versions

### 1. Full Verbose Prompts (Phase 1-2)
- **Location**: `app/services/prompt_en.py` (English), `app/services/prompt_cn.py` (Chinese)
- **Status**: Deprecated, replaced by compact versions
- **Token Usage**: ~2-3x more tokens than compact versions
- **Preserved for**: Historical reference, quality comparison

### 2. Prompt Manager Templates
- **Location**: `prompts/active/*.txt`
- **Status**: Partially deprecated
- **Note**: Some templates match current compact versions, others are outdated

## Migration History

### Phase 1: Initial Implementation
- Full verbose prompts with detailed instructions
- Separate files for each language
- No token optimization

### Phase 2: Token Optimization
- Introduction of compact prompts
- Reduced token usage by 40-50%
- Maintained quality

### Phase 3: Output Optimization
- Further optimization with reasoning control
- Version tracking system
- Dynamic prompt assembly
- Total optimization: ~60% token reduction

## Comparison

| Version | Input Tokens | Output Tokens | Total | Quality |
|---------|-------------|---------------|-------|---------|
| Full Verbose | ~900 | ~400 | ~1,300 | High |
| Compact V1 | ~700 | ~400 | ~1,100 | High |
| Compact V2 | ~700 | ~300 | ~1,000 | High |
| Compact V2 Optimized | ~700 | ~200 | ~900 | High |

## Usage

These legacy prompts should NOT be used in production. They are preserved for:
1. Historical documentation
2. A/B testing comparisons
3. Quality benchmarking
4. Training new team members
5. Understanding system evolution

## See Also

- `PROMPT_VERSION_COMPARISON_REPORT.md` - Detailed comparison of all versions
- `app/services/prompt_compact.py` - Current compact prompts
- `app/services/prompt_assembler.py` - Dynamic prompt assembly
