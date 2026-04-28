export type QuestionType = "single" | "multi" | "single_image" | "text";

export interface QuestionOption {
  id: string;
  label: string;
  image?: string;
}

export interface ConditionalOn {
  question_id: string;
  value_not_in: string[];
}

export interface Question {
  id: string;
  prompt: string;
  type: QuestionType;
  maps_to: string;
  options: QuestionOption[];
  max_select?: number;
  conditional_on?: ConditionalOn;
  skip_value?: string;
  wrap_in_list?: boolean;
  placeholder?: string;
  max_length?: number;
  optional?: boolean;
}

export interface Quiz {
  version: number;
  questions: Question[];
}

export type AnswerValue = string | string[];
export type Answers = Record<string, AnswerValue>;

export interface HairProfile {
  curl_pattern: string;
  scalp_condition: string;
  density: string;
  strand_thickness: string;
  chemical_treatment: string;
  heat_tool_frequency: string;
  concerns: string[];
  goals: string[];
  product_absorption: string;
  wash_frequency: string;
  climate: string;
  story?: string;
}
