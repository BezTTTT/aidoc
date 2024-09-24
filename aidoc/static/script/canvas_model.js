// export interface Property {
//     lineWidth?: number
//     strokeColor?: string
//     fillColor?: string
// }

export class CanvasShape {
    constructor(x, y, property) {
        this.startX = x
        this.startY = y
        if (property) {
            this.property = property
        }
    }
}

export class Line extends CanvasShape {
    constructor(x1, y1, x2, y2, property) {
        super(x1, y1, property)
        this.endX = x2
        this.endY = y2
    }
}

// export class Rectangle extends CanvasShape {
//     constructor(x, y, width, height, property) {
//         super(x, y, property)
//         this.width = width
//         this.height = height
//     }
// }

// export class FillRectangle extends Rectangle {
//     constructor(x: number, y: number, width: number, height: number, property?: Property) {
//         super(x, y, width, height, property)
//     }
// }

// export class StrokeRectangle extends Rectangle {
//     constructor(x: number, y: number, width: number, height: number, property?: Property) {
//         super(x, y, width, height, property)
//     }
// }

export class Circle extends CanvasShape {
    constructor(x, y, radius, startAngle, endAngle, counterclockwise, property) {
        super(x, y, property)
        this.radius = radius
        this.startAngle = startAngle
        this.endAngle = endAngle
        this.counterclockwise = counterclockwise
    }
}

export class FillCircle extends Circle {
    constructor(x, y, radius, startAngle, endAngle, counterclockwise, property) {
        super(x, y, radius, startAngle, endAngle, counterclockwise, property)
    }
}

export class StrokeCircle extends Circle {
    constructor(x, y, radius, startAngle, endAngle, counterclockwise, property) {
        super(x, y, radius, startAngle, endAngle, counterclockwise, property)
    }
}