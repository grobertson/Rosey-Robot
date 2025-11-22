# Technical Specification: CPU Overhead Investigation

**Sprint**: Sprint 10.5 "The French Connection II"  
**Sortie**: 4 of 4  
**Estimated Effort**: 3 hours  
**Dependencies**: Sprint 10 Sortie 4 (benchmark baseline)  

---

## Overview

Investigate 5.80% CPU overhead (vs 5% P1 target) in NATS architecture. Profile operations, identify hotspots, and document findings with optimization recommendations.

---

## Methodology

### 1. Profile NATS Operations

**Tool**: Python cProfile + pstats

**Script**: `tests/performance/profile_nats.py` (NEW)

```python
#!/usr/bin/env python3
"""Profile NATS operations to identify CPU hotspots."""
import asyncio
import cProfile
import pstats
import json
from io import StringIO
from common.database_service import DatabaseService
from nats.aio.client import Client as NATS

async def profile_nats_operations():
    """Profile 1000 NATS publish operations."""
    # Connect to NATS
    nc = NATS()
    await nc.connect(servers=["nats://localhost:4222"])
    
    # Create database service
    db_service = DatabaseService(nats_client=nc, db_path=':memory:')
    await db_service.start()
    
    # Profile 1000 chat events
    data = json.dumps({
        'username': 'TestUser',
        'message': 'Test message',
        'timestamp': 1234567890
    }).encode()
    
    for _ in range(1000):
        await nc.publish('rosey.events.chat', data)
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    # Cleanup
    await db_service.stop()
    await nc.close()

if __name__ == '__main__':
    # Run with profiling
    profiler = cProfile.Profile()
    profiler.enable()
    
    asyncio.run(profile_nats_operations())
    
    profiler.disable()
    
    # Generate report
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs()
    stats.sort_stats('cumulative')
    stats.print_stats(50)  # Top 50 functions
    
    # Save to file
    with open('nats_profile.txt', 'w') as f:
        f.write(stream.getvalue())
    
    print("Profile saved to nats_profile.txt")
    print("\nTop 10 CPU-intensive functions:")
    stats.print_stats(10)
```

**Run**:
```bash
python tests/performance/profile_nats.py
```

---

### 2. Profile Direct Database Operations

**Script**: `tests/performance/profile_direct.py` (NEW)

```python
#!/usr/bin/env python3
"""Profile direct database operations (no NATS) for comparison."""
import asyncio
import cProfile
import pstats
from io import StringIO
from common.database import BotDatabase

async def profile_direct_operations():
    """Profile 1000 direct database writes."""
    # Connect to database
    db = BotDatabase(':memory:')
    await db.connect()
    
    # Profile 1000 chat logs
    for i in range(1000):
        await db.log_chat('TestUser', f'Test message {i}')
    
    # Cleanup
    await db.close()

if __name__ == '__main__':
    # Run with profiling
    profiler = cProfile.Profile()
    profiler.enable()
    
    asyncio.run(profile_direct_operations())
    
    profiler.disable()
    
    # Generate report
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs()
    stats.sort_stats('cumulative')
    stats.print_stats(50)
    
    # Save to file
    with open('direct_profile.txt', 'w') as f:
        f.write(stream.getvalue())
    
    print("Profile saved to direct_profile.txt")
    print("\nTop 10 CPU-intensive functions:")
    stats.print_stats(10)
```

**Run**:
```bash
python tests/performance/profile_direct.py
```

---

### 3. Compare Profiles

**Analysis Script**: `tests/performance/compare_profiles.py` (NEW)

```python
#!/usr/bin/env python3
"""Compare NATS vs direct database profiles."""
import pstats
from pstats import SortKey

def compare_profiles():
    """Compare and report differences."""
    nats_stats = pstats.Stats('nats_profile.txt')
    direct_stats = pstats.Stats('direct_profile.txt')
    
    print("="*80)
    print("NATS Architecture CPU Profile")
    print("="*80)
    nats_stats.sort_stats(SortKey.CUMULATIVE)
    nats_stats.print_stats(20)
    
    print("\n" + "="*80)
    print("Direct Database CPU Profile")
    print("="*80)
    direct_stats.sort_stats(SortKey.CUMULATIVE)
    direct_stats.print_stats(20)
    
    print("\n" + "="*80)
    print("Analysis")
    print("="*80)
    print("NATS overhead functions likely include:")
    print("- nats.aio.client (publish/subscribe)")
    print("- json.dumps/loads (serialization)")
    print("- asyncio event loop operations")
    print("\nRecommendation: Document top 3 hotspots and assess if optimization needed.")

if __name__ == '__main__':
    compare_profiles()
```

---

### 4. Write Analysis Document

**File**: `docs/sprints/active/10.5-The-French-Connection-II/CPU_OVERHEAD_ANALYSIS.md` (NEW)

**Template**:

```markdown
# CPU Overhead Analysis

**Date**: [Date]  
**Benchmark**: NATS Architecture vs Direct Database  
**Finding**: 5.80% overhead (target 5%)  

---

## Methodology

1. Profiled 1000 NATS publish operations (cProfile)
2. Profiled 1000 direct database writes (cProfile)
3. Compared cumulative time for top 50 functions
4. Identified top 3 CPU hotspots

---

## Results

### Top 3 Hotspots

1. **[Function Name]**
   - Time: X.XXX seconds (XX% of total)
   - Calls: N
   - Source: [nats.aio.client / json / asyncio]
   - Description: [What this function does]

2. **[Function Name]**
   - Time: X.XXX seconds (XX% of total)
   - Calls: N
   - Source: [...]
   - Description: [...]

3. **[Function Name]**
   - Time: X.XXX seconds (XX% of total)
   - Calls: N
   - Source: [...]
   - Description: [...]

---

## Analysis

### NATS Overhead Breakdown

- JSON serialization: X%
- NATS publish: X%
- Network I/O: X%
- Event loop overhead: X%
- Other: X%

### Comparison to Direct Database

- Direct database: 100% (baseline)
- NATS architecture: 105.80%
- **Overhead: 5.80%**

---

## Recommendations

### Priority 1: No Action Needed ✅

If overhead is primarily from:
- JSON serialization (necessary for NATS)
- Network I/O (inherent to event-driven architecture)
- Event loop context switching (small cost for decoupling)

**Justification**: 5.80% overhead is acceptable trade-off for:
- Clean service separation
- Independent scaling
- Simplified testing
- Real-time event streaming

### Priority 2: Optimize (if applicable)

If hotspots include:
- Inefficient serialization (e.g., double encoding)
- Unnecessary data copies
- Synchronous blocking operations

**Actions**:
1. [Specific optimization 1]
2. [Specific optimization 2]
3. Target: Reduce overhead to <5%

---

## Conclusion

[Summarize findings and recommendation]

**Recommendation**: [Accept overhead / Optimize in Sprint 11 / Investigate further]
```

---

## Deliverables

1. **Profile Scripts** (3 files):
   - `profile_nats.py` - Profile NATS operations
   - `profile_direct.py` - Profile direct database
   - `compare_profiles.py` - Compare results

2. **Profile Data** (2 files):
   - `nats_profile.txt` - cProfile output for NATS
   - `direct_profile.txt` - cProfile output for direct

3. **Analysis Document**:
   - `CPU_OVERHEAD_ANALYSIS.md` - Findings and recommendations

---

## Acceptance Criteria

- [ ] All 3 profile scripts created and run successfully
- [ ] Top 3 CPU hotspots identified
- [ ] Overhead breakdown documented (JSON, NATS, I/O, event loop)
- [ ] Comparison shows 5.80% overhead is reproducible
- [ ] Analysis document written with clear recommendation
- [ ] Recommendation: Accept overhead OR optimize in Sprint 11

---

## Success Metrics

**Before Investigation**:
- Understanding: None (5.80% unexplained)
- Hotspots: Unknown
- Optimization plan: None

**After Investigation**:
- Understanding: Complete (overhead explained)
- Hotspots: Top 3 identified
- Optimization plan: Documented

---

**Estimated Time**: 3 hours  
- Profiling: 1 hour
- Analysis: 1 hour
- Documentation: 1 hour

**Files Created**: 6 (3 scripts, 2 profiles, 1 analysis doc)
