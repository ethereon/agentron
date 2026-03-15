export const Icons = {
    Check: '<path d="M6.333 12 3 8.596l1.167-1.192 2.166 2.213L11.833 4 13 5.191z"/>',
    ChevronDown:
        '<path d="M8 11a.671.671 0 0 1-.301-.069.886.886 0 0 1-.267-.207L4.201 7.251A.72.72 0 0 1 4 6.736c0-.132.032-.255.096-.368a.726.726 0 0 1 .249-.271.654.654 0 0 1 .35-.097.7.7 0 0 1 .515.235l2.794 3.03 2.79-3.03a.677.677 0 0 1 .861-.138.726.726 0 0 1 .249.271.736.736 0 0 1 .096.368.73.73 0 0 1-.197.515l-3.231 3.473a.866.866 0 0 1-.27.207A.742.742 0 0 1 8 11"/>',
    ChevronRight:
        '<path d="M11 8a.671.671 0 0 1-.069.301.886.886 0 0 1-.207.267l-3.473 3.231a.72.72 0 0 1-.515.201.736.736 0 0 1-.368-.096.726.726 0 0 1-.271-.249.654.654 0 0 1-.097-.35.7.7 0 0 1 .235-.515l3.03-2.794-3.03-2.79a.677.677 0 0 1-.138-.861.726.726 0 0 1 .271-.249A.736.736 0 0 1 6.736 4a.73.73 0 0 1 .515.197l3.473 3.231a.866.866 0 0 1 .207.27A.74.74 0 0 1 11 8"/>',
    Cross: '<path d="M4.21 11.79a.705.705 0 0 1-.19-.328.785.785 0 0 1 .005-.377.682.682 0 0 1 .18-.32L6.963 8l-2.76-2.761a.681.681 0 0 1-.179-.32.829.829 0 0 1 0-.376.725.725 0 0 1 .184-.33.654.654 0 0 1 .329-.188.848.848 0 0 1 .382 0 .658.658 0 0 1 .323.18l2.76 2.756 2.755-2.757c.09-.09.198-.15.324-.179a.736.736 0 0 1 .706.189.705.705 0 0 1 .188.329.746.746 0 0 1-.179.7L9.042 8l2.755 2.762c.09.09.15.198.179.324a.787.787 0 0 1-.005.377.67.67 0 0 1-.184.329.67.67 0 0 1-.328.184.785.785 0 0 1-.377.004.642.642 0 0 1-.324-.183L8.003 9.039l-2.76 2.762a.676.676 0 0 1-.323.174.745.745 0 0 1-.377 0 .699.699 0 0 1-.334-.184"/>'
};

const enum DefaultIconSize {
    Width = 16,
    Height = 16
}

interface MakeSvgParams {
    code?: string;
    width?: number | string;
    height?: number | string;
    fill?: string;
}

export function makeSvg(params: MakeSvgParams): SVGSVGElement {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', (params.width ?? DefaultIconSize.Width).toString());
    svg.setAttribute('height', (params.height ?? DefaultIconSize.Height).toString());
    svg.setAttribute('fill', params.fill ?? 'none');
    if (params.code != null) {
        svg.innerHTML = params.code;
    }
    return svg;
}

export type IconName = keyof typeof Icons;

class IconFactory {
    declare private readonly svgContainerTemplate;
    private readonly nameToSvg = new Map<IconName, SVGSVGElement>();

    constructor() {
        this.svgContainerTemplate = makeSvg({
            width: DefaultIconSize.Width,
            height: DefaultIconSize.Height,
            fill: 'currentColor'
        });
        this.svgContainerTemplate.style.display = 'block';
    }

    make(key: IconName): SVGSVGElement {
        let elem = this.nameToSvg.get(key);
        if (elem == null) {
            // Create template SVG for this icon
            elem = this.svgContainerTemplate.cloneNode() as SVGSVGElement;
            elem.innerHTML = Icons[key];
            this.nameToSvg.set(key, elem);
        }
        return elem.cloneNode(true) as SVGSVGElement;
    }
}

const iconFactory = new IconFactory();
export const makeIcon = iconFactory.make.bind(iconFactory);
