import type { Candidate, WorkspaceFilters } from '../../types/domain';

export type CandidateSort = 'Recently updated' | 'Newest first' | 'Name A-Z';

export function buildStatusCounts(candidates: Candidate[]): Record<string, number> {
    return {
        'Under review': countCandidateStatus(candidates, 'Under review'),
        Approved: countCandidateStatus(candidates, 'Approved'),
        'Code assigned': countCandidateStatus(candidates, 'Code assigned'),
        Waitlisted: countCandidateStatus(candidates, 'Waitlisted'),
        Rejected: countCandidateStatus(candidates, 'Rejected'),
    };
}

export function selectCandidates(candidates: Candidate[], query: string, filters: WorkspaceFilters, sort: CandidateSort): Candidate[] {
    const needle = query.trim().toLowerCase();
    return candidates.filter(candidate => (!needle || `${candidate.name} ${candidate.company} ${candidate.telegram}`.toLowerCase().includes(needle)) && (filters.status === 'All' || candidate.status === filters.status) && (filters.wave === 'All' || candidate.wave === filters.wave) && (filters.source === 'All' || candidate.source === filters.source) && (!filters.expertise || filters.expertise === 'All' || candidate.expertise === filters.expertise)).sort((a, b) => sort === 'Name A-Z' ? a.name.localeCompare(b.name) : sort === 'Newest first' ? b.appliedAt.localeCompare(a.appliedAt) : 0);
}

export function countCandidateStatus(candidates: Candidate[], status: Candidate['status']): number { return candidates.filter(candidate => candidate.status === status).length }
