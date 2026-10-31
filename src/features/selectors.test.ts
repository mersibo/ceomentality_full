import { describe, expect, it } from 'vitest';
import { buildStatusCounts, countCandidateStatus, selectCandidates } from './candidates/selectors';
import { selectBatches } from './access/selectors';
import type { AccessBatch, Candidate, WorkspaceFilters } from '../types/domain';

const filters: WorkspaceFilters = { status: 'All', wave: 'All', source: 'All', expertise: 'All' };
const candidate = (overrides: Partial<Candidate> = {}): Candidate => ({
    id: 'candidate-1', name: 'Alexei Petrov', initials: 'AP', role: 'Founder', company: 'Northtrail',
    status: 'Under review', wave: 'Wave 01', code: null, notes: [], summary: 'Builder', expertise: 'Founder / CEO',
    country: 'Switzerland', telegram: '@alexei', source: 'Website', stage: 'purchase', appliedAt: '2025-05-01', ...overrides
});
const batch = (overrides: Partial<AccessBatch> = {}): AccessBatch => ({
    id: 'batch-1', name: 'Wave 01', description: 'Spring Collection Drop', issued: 100, redeemed: 25,
    status: 'Active', validity: 'May 1 - May 31, 2025', code: 'CM-WAVE01', ...overrides
});

describe('candidate selectors', () => {
    it('combines search and filters without mutating records', () => {
        const source = [candidate(), candidate({ id: 'candidate-2', name: 'Maria Ivanova', status: 'Approved', source: 'Partner' })];
        expect(selectCandidates(source, 'maria', { ...filters, status: 'Approved', source: 'Partner' }, 'Recently updated')).toEqual([source[1]]);
        expect(source).toHaveLength(2);
    });
    it('counts statuses', () => expect(countCandidateStatus([candidate(), candidate({ id: 'candidate-2' })], 'Under review')).toBe(2));
    it('builds sidebar status counts from backend candidates', () => {
        const source = [candidate(), candidate({ id: 'candidate-2', status: 'Approved' }), candidate({ id: 'candidate-3', status: 'Waitlisted' }), candidate({ id: 'candidate-4', status: 'Rejected' }), candidate({ id: 'candidate-5', status: 'Code assigned' })];
        expect(buildStatusCounts(source)).toEqual({
            'Under review': 1,
            Approved: 1,
            'Code assigned': 1,
            Waitlisted: 1,
            Rejected: 1,
        });
    });
});

describe('batch selectors', () => {
    it('filters expired batches and sorts by issued count', () => {
        const source = [batch(), batch({ id: 'batch-2', name: 'Archive', status: 'Closed', issued: 500 })];
        expect(selectBatches(source, '', { ...filters, status: 'Expired' }, 'All', 'Highest issued').map(item => item.id)).toEqual(['batch-2']);
    });
    it('searches access codes', () => expect(selectBatches([batch()], 'cm-wave', filters, 'All', 'Recently created')).toHaveLength(1));
});
