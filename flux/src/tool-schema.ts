export interface JsonSchemaObject {
    type: 'object';
    properties?: Record<string, JsonSchema>;
    required?: string[];
    description?: string;
}

export interface JsonSchemaArray {
    type: 'array';
    items?: JsonSchema;
    description?: string;
}

export interface JsonSchemaScalar {
    type?: string | string[];
    description?: string;
    enum?: unknown[];
    format?: string;
    minimum?: number;
    maximum?: number;
    minLength?: number;
    maxLength?: number;
    default?: unknown;
}

export interface JsonSchemaAnyOf {
    anyOf: JsonSchema[];
    description?: string;
}

export type JsonSchema = JsonSchemaObject | JsonSchemaArray | JsonSchemaScalar | JsonSchemaAnyOf;

export interface ToolSchema {
    name: string;
    description?: string;
    parameters: JsonSchemaObject;
}
