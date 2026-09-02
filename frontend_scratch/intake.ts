export type Provenance = 'EXPLICIT_USER' | 'LLM_INFERRED' | 'SYSTEM_DEFAULT' | 'USER_CONFIRMED';

export interface ProvenancedString {
  value: string;
  provenance: Provenance;
}

export interface ProvenancedList {
  value: string[];
  provenance: Provenance;
}

export interface ProvenancedInt {
  value: number | null;
  provenance: Provenance;
}

export interface TargetSpecification {
  entity_type: ProvenancedString;
  description: ProvenancedString;
  industries: ProvenancedList;
  categories: ProvenancedList;
}

export interface GeographySpecification {
  countries: ProvenancedList;
  regions: ProvenancedList;
  cities: ProvenancedList;
  radius: ProvenancedInt;
  scope: ProvenancedString;
}

export interface CompanyConstraintsSpecification {
  min_employees: ProvenancedInt;
  max_employees: ProvenancedInt;
  min_revenue: ProvenancedInt;
  max_revenue: ProvenancedInt;
  company_types: ProvenancedList;
}

export interface PeopleConstraintsSpecification {
  roles: ProvenancedList;
  departments: ProvenancedList;
  seniority: ProvenancedList;
  functions: ProvenancedList;
}

export interface ProspectingSpecification {
  objective_type: ProvenancedString;
  objective: ProvenancedString;
  target: TargetSpecification;
  geography: GeographySpecification;
  company_constraints: CompanyConstraintsSpecification;
  people_constraints: PeopleConstraintsSpecification;
  exclusion_rules: ProvenancedList;
  requested_information: ProvenancedList;
  research_depth: ProvenancedString;
}

export interface IntakeRequest {
  id: string;
  raw_objective: string;
  raw_target: string;
  raw_qualification: string;
  clarification_history: Array<{ question: string; answer: string }>;
  status: 'DRAFT' | 'PARSING' | 'NEEDS_CLARIFICATION' | 'READY_FOR_REVIEW' | 'CONFIRMED' | 'EXECUTING' | 'CANCELLED';
  created_at: string;
}

export interface SpecificationVersion {
  id: string;
  version: number;
  specification_json: ProspectingSpecification;
  status: 'DRAFT' | 'READY_FOR_REVIEW' | 'CONFIRMED';
  parser_model: string;
  parser_provider: string;
}
