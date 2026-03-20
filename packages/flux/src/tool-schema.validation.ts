import type { ToolSchema } from './tool-schema.js';

// --- AUTO-GENERATED CODE BELOW --- //

function isJsonSchemaScalar(obj: any): boolean {
    return (
        obj != null &&
        (obj.type == null ||
            typeof obj.type === 'string' ||
            (Array.isArray(obj.type) && obj.type.every((item: any) => typeof item === 'string'))) &&
        (obj.description == null || typeof obj.description === 'string') &&
        (obj.enum == null ||
            (Array.isArray(obj.enum) && obj.enum.every((item: any) => item != null))) &&
        (obj.format == null || typeof obj.format === 'string') &&
        (obj.minimum == null || typeof obj.minimum === 'number') &&
        (obj.maximum == null || typeof obj.maximum === 'number') &&
        (obj.minLength == null || typeof obj.minLength === 'number') &&
        (obj.maxLength == null || typeof obj.maxLength === 'number')
    );
}

function isJsonSchemaAnyOf(obj: any): boolean {
    return (
        obj != null &&
        Array.isArray(obj.anyOf) &&
        obj.anyOf.every(
            (item: any) =>
                isJsonSchemaObject(item) ||
                isJsonSchemaArray(item) ||
                isJsonSchemaScalar(item) ||
                isJsonSchemaAnyOf(item)
        ) &&
        (obj.description == null || typeof obj.description === 'string')
    );
}

function isJsonSchemaArray(obj: any): boolean {
    return (
        obj != null &&
        obj.type === 'array' &&
        (obj.items == null ||
            isJsonSchemaObject(obj.items) ||
            isJsonSchemaArray(obj.items) ||
            isJsonSchemaScalar(obj.items) ||
            isJsonSchemaAnyOf(obj.items)) &&
        (obj.description == null || typeof obj.description === 'string')
    );
}

function isJsonSchemaObject(obj: any): boolean {
    return (
        obj != null &&
        obj.type === 'object' &&
        (obj.properties == null ||
            (obj.properties != null &&
                typeof obj.properties === 'object' &&
                !Array.isArray(obj.properties) &&
                Object.values(obj.properties).every(
                    (value: any) =>
                        isJsonSchemaObject(value) ||
                        isJsonSchemaArray(value) ||
                        isJsonSchemaScalar(value) ||
                        isJsonSchemaAnyOf(value)
                ))) &&
        (obj.required == null ||
            (Array.isArray(obj.required) &&
                obj.required.every((item: any) => typeof item === 'string'))) &&
        (obj.description == null || typeof obj.description === 'string')
    );
}

export function isToolSchema(obj: any): obj is ToolSchema {
    return (
        obj != null &&
        typeof obj.name === 'string' &&
        isJsonSchemaObject(obj.parameters) &&
        (obj.description == null || typeof obj.description === 'string')
    );
}
