import { Type, type TSchema, type TObject } from '@sinclair/typebox';
import { StringEnum, type Tool } from '@mariozechner/pi-ai';
import type {
    JsonSchema,
    JsonSchemaAnyOf,
    JsonSchemaArray,
    JsonSchemaObject,
    JsonSchemaScalar,
    ToolSchema
} from '../tool-schema.js';

// ---- Helpers ----

function isAnyOf(schema: JsonSchema): schema is JsonSchemaAnyOf {
    return 'anyOf' in schema && Array.isArray((schema as JsonSchemaAnyOf).anyOf);
}

function getOpts(schema: JsonSchema): Record<string, unknown> {
    const s = schema as JsonSchemaScalar;
    return s.description ? { description: s.description } : {};
}

// ---- Converter ----

/**
 * Converts a single JSON Schema node to a TypeBox TSchema.
 */
function jsonSchemaToTypeBox(schema: JsonSchema): TSchema {
    const opts = getOpts(schema);

    // anyOf: union type, e.g. { anyOf: [{type: 'string'}, {type: 'null'}] }
    // also covers the nullable shorthand OpenAI uses for optional tool params
    if (isAnyOf(schema)) {
        const variants = schema.anyOf.map(jsonSchemaToTypeBox);

        // Collapse single-item unions (shouldn't happen, but be safe)
        if (variants.length === 1) return variants[0];

        // Check if this is a simple T | null pattern → Type.Union still, but
        // keep it as-is since TypeBox handles T | null fine via Union.
        return Type.Union(variants, opts);
    }

    const scalar = schema as JsonSchemaScalar;

    // Nullable via type array: { type: ["number", "null"] }
    if (Array.isArray(scalar.type)) {
        const nonNull = scalar.type.filter(t => t !== 'null');
        const isNullable = scalar.type.includes('null');
        const inner = jsonSchemaToTypeBox({ ...schema, type: nonNull[0] } as JsonSchema);
        return isNullable ? Type.Union([inner, Type.Null()], opts) : inner;
    }

    const obj = schema as JsonSchemaObject;
    const arr = schema as JsonSchemaArray;

    switch (scalar.type) {
        case 'object': {
            const props: Record<string, TSchema> = {};
            const required = new Set(obj.required ?? []);

            for (const [key, value] of Object.entries(obj.properties ?? {})) {
                const converted = jsonSchemaToTypeBox(value);
                props[key] = required.has(key) ? converted : Type.Optional(converted);
            }

            return Type.Object(props, opts);
        }

        case 'array':
            return Type.Array(arr.items ? jsonSchemaToTypeBox(arr.items) : Type.Unknown(), opts);

        case 'string':
            // Use StringEnum for string enums — avoids anyOf/const patterns that
            // Google's API doesn't support (as recommended by the pi README).
            if (scalar.enum && scalar.enum.length > 0) {
                return StringEnum(scalar.enum as string[], {
                    ...opts,
                    ...(scalar.default !== undefined ? { default: scalar.default as string } : {})
                });
            }
            return Type.String({
                ...opts,
                ...(scalar.format ? { format: scalar.format } : {}),
                ...(scalar.minLength !== undefined ? { minLength: scalar.minLength } : {}),
                ...(scalar.maxLength !== undefined ? { maxLength: scalar.maxLength } : {}),
                ...(scalar.default !== undefined ? { default: scalar.default } : {})
            });

        case 'number':
        case 'integer':
            return Type.Number({
                ...opts,
                ...(scalar.minimum !== undefined ? { minimum: scalar.minimum } : {}),
                ...(scalar.maximum !== undefined ? { maximum: scalar.maximum } : {}),
                ...(scalar.default !== undefined ? { default: scalar.default } : {})
            });

        case 'boolean':
            return Type.Boolean({ ...opts });

        case 'null':
            return Type.Null({ ...opts });

        default:
            return Type.Unknown({ ...opts });
    }
}

/**
 * Converts a JSON Schema tool definition (as used by OpenAI/Anthropic APIs)
 * to a pi-compatible Tool definition backed by TypeBox.
 */
export function jsonSchemaToolToPiTool(schemaTool: ToolSchema): Tool {
    const parameters = jsonSchemaToTypeBox(schemaTool.parameters) as TObject;

    return {
        name: schemaTool.name,
        description: schemaTool.description ?? '',
        parameters
    };
}
