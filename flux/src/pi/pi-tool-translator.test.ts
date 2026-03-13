import { describe, it, expect } from 'vitest';
import { Kind, OptionalKind } from '@sinclair/typebox';
import { jsonSchemaToolToPiTool } from './pi-tool-translator.js';

function kind(schema: any): string {
    return schema[Kind];
}

function isOptional(schema: any): boolean {
    return schema[OptionalKind] === 'Optional';
}

describe('jsonSchemaToolToPiTool', () => {
    // ---- Top-level tool shape ----

    describe('tool metadata', () => {
        it('copies name and description', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 'my_tool',
                description: 'Does a thing',
                parameters: { type: 'object', properties: {} }
            });
            expect(tool.name).toBe('my_tool');
            expect(tool.description).toBe('Does a thing');
        });

        it('uses empty string when description is missing', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 'no_desc',
                parameters: { type: 'object', properties: {} }
            });
            expect(tool.description).toBe('');
        });

        it('returns an Object schema at the top level', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: { type: 'object', properties: {} }
            });
            expect(kind(tool.parameters)).toBe('Object');
        });
    });

    // ---- Scalar types ----

    describe('scalar types', () => {
        function paramSchema(propType: any) {
            return jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['x'],
                    properties: { x: propType }
                }
            }).parameters.properties.x;
        }

        it('maps string → String', () => {
            expect(kind(paramSchema({ type: 'string' }))).toBe('String');
        });

        it('maps number → Number', () => {
            expect(kind(paramSchema({ type: 'number' }))).toBe('Number');
        });

        it('maps integer → Number', () => {
            expect(kind(paramSchema({ type: 'integer' }))).toBe('Number');
        });

        it('maps boolean → Boolean', () => {
            expect(kind(paramSchema({ type: 'boolean' }))).toBe('Boolean');
        });

        it('maps null → Null', () => {
            expect(kind(paramSchema({ type: 'null' }))).toBe('Null');
        });

        it('maps unknown type → Unknown', () => {
            expect(kind(paramSchema({ type: 'this-is-not-a-type' }))).toBe('Unknown');
        });

        it('maps missing type → Unknown', () => {
            expect(kind(paramSchema({}))).toBe('Unknown');
        });
    });

    // ---- String constraints ----

    describe('string constraints', () => {
        function strParam(extra: object) {
            return jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['x'],
                    properties: { x: { type: 'string', ...extra } }
                }
            }).parameters.properties.x;
        }

        it('forwards format', () => {
            expect(strParam({ format: 'date-time' }).format).toBe('date-time');
        });

        it('forwards minLength', () => {
            expect(strParam({ minLength: 2 }).minLength).toBe(2);
        });

        it('forwards maxLength', () => {
            expect(strParam({ maxLength: 100 }).maxLength).toBe(100);
        });

        it('forwards default', () => {
            expect(strParam({ default: 'hello' }).default).toBe('hello');
        });
    });

    // ---- Number constraints ----

    describe('number constraints', () => {
        function numParam(extra: object) {
            return jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['x'],
                    properties: { x: { type: 'number', ...extra } }
                }
            }).parameters.properties.x;
        }

        it('forwards minimum', () => {
            expect(numParam({ minimum: 0 }).minimum).toBe(0);
        });

        it('forwards maximum', () => {
            expect(numParam({ maximum: 100 }).maximum).toBe(100);
        });

        it('forwards default', () => {
            expect(numParam({ default: 42 }).default).toBe(42);
        });
    });

    // ---- Descriptions ----

    describe('descriptions', () => {
        it('forwards description on a scalar property', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['x'],
                    properties: { x: { type: 'string', description: 'the x value' } }
                }
            });
            expect(tool.parameters.properties.x.description).toBe('the x value');
        });

        it('forwards description on a nested object', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['pt'],
                    properties: {
                        pt: {
                            type: 'object',
                            description: 'a point',
                            properties: { x: { type: 'number' } }
                        }
                    }
                }
            });
            expect(tool.parameters.properties.pt.description).toBe('a point');
        });

        it('forwards description on an array', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['tags'],
                    properties: {
                        tags: {
                            type: 'array',
                            description: 'list of tags',
                            items: { type: 'string' }
                        }
                    }
                }
            });
            expect(tool.parameters.properties.tags.description).toBe('list of tags');
        });
    });

    // ---- Required vs optional ----

    describe('required / optional', () => {
        it('marks required fields as non-optional', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['a'],
                    properties: {
                        a: { type: 'string' },
                        b: { type: 'string' }
                    }
                }
            });
            expect(isOptional(tool.parameters.properties.a)).toBe(false);
            expect(isOptional(tool.parameters.properties.b)).toBe(true);
        });

        it('makes all fields optional when required is absent', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    properties: { x: { type: 'number' } }
                }
            });
            expect(isOptional(tool.parameters.properties.x)).toBe(true);
        });

        it('makes all fields optional when required is empty', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: [],
                    properties: { x: { type: 'number' } }
                }
            });
            expect(isOptional(tool.parameters.properties.x)).toBe(true);
        });

        it('required field still has correct underlying Kind', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['x'],
                    properties: { x: { type: 'string' } }
                }
            });
            expect(kind(tool.parameters.properties.x)).toBe('String');
            expect(isOptional(tool.parameters.properties.x)).toBe(false);
        });

        it('optional field still has correct underlying Kind', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    properties: { x: { type: 'number' } }
                }
            });
            expect(kind(tool.parameters.properties.x)).toBe('Number');
            expect(isOptional(tool.parameters.properties.x)).toBe(true);
        });
    });

    // ---- Arrays ----

    describe('array type', () => {
        it('maps array with string items', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['tags'],
                    properties: { tags: { type: 'array', items: { type: 'string' } } }
                }
            });
            const tags = tool.parameters.properties.tags;
            expect(kind(tags)).toBe('Array');
            expect(kind(tags.items)).toBe('String');
        });

        it('maps array without items → Unknown items', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['things'],
                    properties: { things: { type: 'array' } }
                }
            });
            expect(kind(tool.parameters.properties.things.items)).toBe('Unknown');
        });

        it('maps array of objects', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['pts'],
                    properties: {
                        pts: {
                            type: 'array',
                            items: {
                                type: 'object',
                                required: ['x', 'y'],
                                properties: { x: { type: 'number' }, y: { type: 'number' } }
                            }
                        }
                    }
                }
            });
            const pts = tool.parameters.properties.pts;
            expect(kind(pts)).toBe('Array');
            expect(kind(pts.items)).toBe('Object');
            expect(kind(pts.items.properties.x)).toBe('Number');
        });
    });

    // ---- Nested objects ----

    describe('nested objects', () => {
        it('maps deeply nested object', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 'render_point',
                description: 'Renders a point on the screen.',
                parameters: {
                    type: 'object',
                    required: ['point'],
                    properties: {
                        point: {
                            type: 'object',
                            required: ['x', 'y'],
                            properties: {
                                x: { type: 'number' },
                                y: { type: 'number' },
                                opacity: { type: 'number' }
                            }
                        }
                    }
                }
            });
            const pt = tool.parameters.properties.point;
            expect(kind(pt)).toBe('Object');
            expect(kind(pt.properties.x)).toBe('Number');
            expect(isOptional(pt.properties.x)).toBe(false);
            expect(kind(pt.properties.y)).toBe('Number');
            expect(isOptional(pt.properties.y)).toBe(false);
            expect(kind(pt.properties.opacity)).toBe('Number');
            expect(isOptional(pt.properties.opacity)).toBe(true);
        });
    });

    // ---- StringEnum ----

    describe('StringEnum', () => {
        function enumParam(extra: object = {}) {
            return jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['units'],
                    properties: {
                        units: { type: 'string', enum: ['celsius', 'fahrenheit'], ...extra }
                    }
                }
            }).parameters.properties.units;
        }

        it('uses StringEnum (Kind = Unsafe) for string enums, not plain String', () => {
            expect(kind(enumParam())).toBe('Unsafe');
        });

        it('StringEnum carries the correct enum values', () => {
            const schema = enumParam() as any;
            expect(schema.enum).toEqual(['celsius', 'fahrenheit']);
        });

        it('StringEnum has type: string', () => {
            expect((enumParam() as any).type).toBe('string');
        });

        it('forwards default on StringEnum', () => {
            expect(enumParam({ default: 'celsius' }).default).toBe('celsius');
        });

        it('forwards description on StringEnum', () => {
            expect(enumParam({ description: 'temperature unit' }).description).toBe(
                'temperature unit'
            );
        });

        it('StringEnum is not marked optional when required', () => {
            expect(isOptional(enumParam())).toBe(false);
        });

        it('StringEnum is marked optional when not required', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    properties: { mode: { type: 'string', enum: ['a', 'b'] } }
                }
            });
            expect(isOptional(tool.parameters.properties.mode)).toBe(true);
            expect(kind(tool.parameters.properties.mode)).toBe('Unsafe');
        });

        it('does NOT use StringEnum for plain string without enum', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['s'],
                    properties: { s: { type: 'string' } }
                }
            });
            expect(kind(tool.parameters.properties.s)).toBe('String');
        });
    });

    // ---- Nullable via type array ----

    describe('nullable via type array', () => {
        function nullableParam(types: string[]) {
            return jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['x'],
                    properties: { x: { type: types as any } }
                }
            }).parameters.properties.x;
        }

        it('["number","null"] → Union', () => {
            expect(kind(nullableParam(['number', 'null']))).toBe('Union');
        });

        it('["number","null"] union contains Number and Null', () => {
            const schema = nullableParam(['number', 'null']) as any;
            const kinds = schema.anyOf.map((s: any) => kind(s));
            expect(kinds).toContain('Number');
            expect(kinds).toContain('Null');
        });

        it('["string","null"] → Union with String and Null', () => {
            const schema = nullableParam(['string', 'null']) as any;
            const kinds = schema.anyOf.map((s: any) => kind(s));
            expect(kinds).toContain('String');
            expect(kinds).toContain('Null');
        });

        it('single-type array with no null is not a Union', () => {
            expect(kind(nullableParam(['string']))).toBe('String');
        });
    });

    // ---- anyOf ----

    describe('anyOf', () => {
        function anyOfParam(anyOf: object[]) {
            return jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['x'],
                    properties: { x: { anyOf } as any }
                }
            }).parameters.properties.x;
        }

        it('maps anyOf to Union', () => {
            expect(kind(anyOfParam([{ type: 'string' }, { type: 'number' }]))).toBe('Union');
        });

        it('anyOf with null produces Union containing Null', () => {
            const schema = anyOfParam([{ type: 'string' }, { type: 'null' }]) as any;
            const kinds = schema.anyOf.map((s: any) => kind(s));
            expect(kinds).toContain('String');
            expect(kinds).toContain('Null');
        });

        it('anyOf with three variants', () => {
            const schema = anyOfParam([
                { type: 'string' },
                { type: 'number' },
                { type: 'boolean' }
            ]) as any;
            const kinds = schema.anyOf.map((s: any) => kind(s));
            expect(kinds).toContain('String');
            expect(kinds).toContain('Number');
            expect(kinds).toContain('Boolean');
        });

        it('anyOf with nested object variant', () => {
            const schema = anyOfParam([
                { type: 'object', properties: { x: { type: 'number' } }, required: ['x'] },
                { type: 'null' }
            ]) as any;
            const objectVariant = schema.anyOf.find((s: any) => kind(s) === 'Object');
            expect(objectVariant).toBeDefined();
            expect(kind(objectVariant.properties.x)).toBe('Number');
        });

        it('anyOf single item is unwrapped (no Union)', () => {
            expect(kind(anyOfParam([{ type: 'string' }]))).toBe('String');
        });

        it('forwards description on anyOf', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 't',
                parameters: {
                    type: 'object',
                    required: ['x'],
                    properties: {
                        x: {
                            anyOf: [{ type: 'string' }, { type: 'null' }],
                            description: 'flexible'
                        } as any
                    }
                }
            });
            expect(tool.parameters.properties.x.description).toBe('flexible');
        });
    });

    // ---- Complex real-world fixtures ----

    describe('real-world fixture', () => {
        it('converts the render_point schema with nullable opacity', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 'render_point',
                description: 'Renders a point on the screen.',
                parameters: {
                    type: 'object',
                    required: ['point'],
                    properties: {
                        point: {
                            type: 'object',
                            required: ['x', 'y'],
                            properties: {
                                x: { type: 'number' },
                                y: { type: 'number' },
                                opacity: { type: ['number', 'null'] }
                            }
                        }
                    }
                }
            });

            expect(tool.name).toBe('render_point');
            const pt = tool.parameters.properties.point;
            expect(kind(pt)).toBe('Object');
            expect(kind(pt.properties.x)).toBe('Number');
            expect(isOptional(pt.properties.x)).toBe(false);
            expect(kind(pt.properties.y)).toBe('Number');
            expect(isOptional(pt.properties.y)).toBe(false);
            // opacity: optional Union(Number, Null)
            expect(kind(pt.properties.opacity)).toBe('Union');
            expect(isOptional(pt.properties.opacity)).toBe(true);
            const unionKinds = (pt.properties.opacity as any).anyOf.map((s: any) => kind(s));
            expect(unionKinds).toContain('Number');
            expect(unionKinds).toContain('Null');
        });

        it('converts a weather tool with StringEnum and nested array', () => {
            const tool = jsonSchemaToolToPiTool({
                name: 'get_weather',
                description: 'Get current weather for a location',
                parameters: {
                    type: 'object',
                    required: ['location'],
                    properties: {
                        location: { type: 'string', description: 'City name or coordinates' },
                        units: {
                            type: 'string',
                            enum: ['celsius', 'fahrenheit'],
                            default: 'celsius'
                        },
                        days: { type: 'integer', minimum: 1, maximum: 14 },
                        fields: { type: 'array', items: { type: 'string' } }
                    }
                }
            });

            const p = tool.parameters.properties;

            expect(kind(p.location)).toBe('String');
            expect(isOptional(p.location)).toBe(false);

            // units: optional StringEnum
            expect(kind(p.units)).toBe('Unsafe');
            expect(isOptional(p.units)).toBe(true);
            expect((p.units as any).enum).toEqual(['celsius', 'fahrenheit']);
            expect((p.units as any).default).toBe('celsius');

            // days: optional Number with constraints
            expect(kind(p.days)).toBe('Number');
            expect(isOptional(p.days)).toBe(true);
            expect((p.days as any).minimum).toBe(1);
            expect((p.days as any).maximum).toBe(14);

            // fields: optional Array of Strings
            expect(kind(p.fields)).toBe('Array');
            expect(isOptional(p.fields)).toBe(true);
            expect(kind((p.fields as any).items)).toBe('String');
        });
    });
});
