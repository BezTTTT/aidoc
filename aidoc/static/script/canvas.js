import * as constants from './constants.js'

import { 
    Line, 
    FillCircle,
} from './canvas_model.js'

export class Canvas {
    // constructor for create class
    constructor(canvas) {
        if (!canvas) return
        const context = canvas.getContext("2d")
        this.context = context

        // default value
        this.context.lineWidth = constants.kLineWidth // 1
        this.context.fillStyle = constants.kBlackColor
        this.context.strokeStyle = constants.kBlackColor
        this.context.fillColor = constants.kBlackColor
        this.context.strokeColor = constants.kBlackColor
        this.context.lineCap = 'butt'
        this.context.lineJoin = 'miter'
    }

    // methods
    // get default
    getDefaultLineStyle() {
        this.context.globalCompositeOperation = "source-over"
        this.context.lineWidth = constants.kLineWidth // 1 * scale
        this.context.fillStyle = constants.kBlackColor
        this.context.strokeStyle = constants.kBlackColor
        this.context.lineCap = 'butt'
        this.context.lineJoin = 'miter'
    }

    // set width of line
    setLineWidth(size) {
        this.lineWidth = size
    }

    // set color of fill
    setFillColor(color) {
        this.fillColor = color
    }

    // set color of border line
    setStrokeColor(color) {
        this.strokeColor = color
    }

    // set property
    setProperty(property) {
        if (this.context) {
            this.getDefaultLineStyle()
            if (property) {
                this.context.lineWidth = property.lineWidth ? property.lineWidth : constants.kLineWidth
                this.context.fillStyle = property.fillColor ? property.fillColor : constants.kBlackColor
                this.context.strokeStyle = property.strokeColor ? property.strokeColor : constants.kBlackColor
            }else {
                this.context.lineWidth = constants.kLineWidth
                this.context.fillStyle = constants.kBlackColor
                this.context.strokeStyle = constants.kBlackColor
            }
        }
    }

    // create Line Object, start (x1, y1) to end (x2, y2)
    line({ 
        x1, 
        y1, 
        x2, 
        y2 
    }) {
        const line = new Line(
            x1,
            y1,
            x2,
            y2,
            {
                lineWidth: this.lineWidth,
                fillColor: this.fillColor,
                strokeColor: this.strokeColor,
            }
        )

        return line
    }

    // draw line on the canvas screen
    drawLine(line) {
        if (this.context) {
            this.context.beginPath()
            this.context.moveTo(line.startX, line.startY)
            this.context.lineTo(line.endX, line.endY)
            this.context.stroke()
            this.context.closePath()
        }
    }

    // draw line on the canvas screen
    drawLineFocus(line) {
        this.drawFillCircle(
            this.fillCircle({
                x: line.startX,
                y: line.startY,
                radius: 5,
                startAngle: 0,
                endAngle: 2 * Math.PI,
                counterclockwise: false
            })
        )
        this.drawFillCircle(
            this.fillCircle({
                x: line.endX,
                y: line.endY,
                radius: 5,
                startAngle: 0,
                endAngle: 2 * Math.PI,
                counterclockwise: false
            })
        )
    }

    // create Fillcircle Object, center (x, y)
    fillCircle({
        x,
        y,
        radius,
        startAngle,
        endAngle,
        counterclockwise,
    }) {
        const cir = new FillCircle(
            x,
            y,
            radius,
            startAngle,
            endAngle,
            counterclockwise,
            {
                lineWidth: this.lineWidth,
                fillColor: this.fillColor,
                strokeColor: this.strokeColor,
            }
        )
        
        return cir
    }

    // draw fill circle on the canvas screen
    drawFillCircle(cir) {
        if (this.context) {
            this.context.beginPath();
            this.context.arc(
                cir.startX, 
                cir.startY, 
                cir.radius, 
                cir.startAngle, 
                cir.endAngle, 
                cir.counterclockwise
            )
            this.context.fill()
            this.context.closePath()
        }
    }

    // create Strokecircle Object, center (x, y)
    StrokeCircle({
        x,
        y,
        radius,
        startAngle,
        endAngle,
        counterclockwise,
    }) {
        const cir = new FillCircle(
            x,
            y,
            radius,
            startAngle,
            endAngle,
            counterclockwise,
            {
                lineWidth: this.lineWidth,
                fillColor: this.fillColor,
                strokeColor: this.strokeColor,
            }
        )
        
        return cir
    }

    // draw stroke circle on the canvas screen
    drawStrokeCircle(cir) {
        if (this.context) {
            this.context.beginPath();
            this.context.arc(
                cir.startX, 
                cir.startY, 
                cir.radius, 
                cir.startAngle, 
                cir.endAngle, 
                cir.counterclockwise
            )
            this.context.stroke()
            this.context.closePath()
        }
    }


    // draw a shape on the canvas screen
    draw(shape) {
        if (shape) {
            this.setProperty(shape.property)
            if (shape instanceof Line) {
                // Handle Line
                this.drawLine(shape)
            }else if (shape instanceof FillCircle) {
                // Handle FillCircle
                this.drawFillCircle(shape)
            }
        }
    }
    
    // handle focus element
    onFocus(shape) {
        if (shape) {
            this.setProperty(shape.property)
            if (shape instanceof Line) {
                // Handle Line
                this.drawLineFocus(shape)
            }
        }
    }

    // clear canvas by rectangle shape, start (x, y) to end (x1 + width, y1 + height)
    clearRectangle({ 
        x, 
        y, 
        width, 
        height 
    }) {
        this.context?.clearRect(x, y, width, height)
    }

    // check equal objects
    isEqualElement(shape1, shape2) {
        if (shape1 && shape2) {
            if (shape1 instanceof Line && shape2 instanceof Line) {
                // Handle Line
                return (
                    shape1.startX === shape2.startX
                    && shape1.endX === shape2.endX
                    && shape1.startY === shape2.startY
                    && shape1.endY === shape2.endY
                    && shape1.property?.lineWidth === shape2.property?.lineWidth
                    && shape1.property?.strokeColor === shape2.property?.strokeColor
                    && shape1.property?.fillColor === shape2.property?.fillColor
                )
            } else if (shape1 instanceof FillCircle && shape2 instanceof FillCircle) {
                // Handle FillCircle
                return (
                    shape1.startX === shape2.startX
                    && shape1.startY === shape2.startY
                    && shape1.radius === shape2.radius
                    && shape1.startAngle === shape2.startAngle
                    && shape1.endAngle === shape2.endAngle
                    && shape1.counterclockwise === shape2.counterclockwise
                    && shape1.property?.lineWidth === shape2.property?.lineWidth
                    && shape1.property?.strokeColor === shape2.property?.strokeColor
                    && shape1.property?.fillColor === shape2.property?.fillColor
                )
            }
        }
        return false
    }

    // draw start point for paths
    drawStartPoint (x, y, isCloseAble, type, scale) {
        if (this.context) {
            // this.lineWidth = constants.kLineWidth / scale
            this.lineWidth = constants.kLineWidth * 2
            if (isCloseAble) {
                this.context.fillStyle = constants.kWhiteColor
                this.drawFillCircle(
                    this.fillCircle({
                        // this code for panning on canvas-screen
                        radius: 6.5,
                        x: x / scale,
                        y: y / scale,
                        startAngle: 0,
                        endAngle: 2 * Math.PI,
                        counterclockwise: false
                    })
                )
                if (type === 'eraser') {
                    this.context.strokeStyle = constants.kLightRedColor
                }else {
                    this.context.strokeStyle = constants.kSkyBlueColor
                }
                this.drawStrokeCircle(
                    this.StrokeCircle({
                        // this code for panning on canvas-screen
                        radius: 5,
                        x: x / scale,
                        y: y / scale,
                        startAngle: 0,
                        endAngle: 2 * Math.PI,
                        counterclockwise: false
                    })
                )
            }else {
                this.context.fillStyle = constants.kWhiteColor
                this.drawFillCircle(
                    this.fillCircle({
                        // this code for panning on canvas-screen
                        radius: 5.5,
                        x: x / scale,
                        y: y / scale,
                        startAngle: 0,
                        endAngle: 2 * Math.PI,
                        counterclockwise: false
                    })
                )
                if (type === 'eraser') {
                    this.context.fillStyle = constants.kLightRedColor
                }else {
                    this.context.fillStyle = constants.kSkyBlueColor
                }
                this.drawFillCircle(
                    this.fillCircle({
                        // this code for panning on canvas-screen
                        radius: 4,
                        x: x / scale,
                        y: y / scale,
                        startAngle: 0,
                        endAngle: 2 * Math.PI,
                        counterclockwise: false
                    })
                )
            }
            this.context.fillStyle = constants.kBlackColor
            this.lineWidth = constants.kLineWidth
        }
    }

    // run path for create/remove fill shape
    runPath(
        points, 
        isCloseAble, 
        type, 
        scale, 
        isMarking,
        pointState 
    ) {
        if (this.context) {
            this.context.globalCompositeOperation = "source-over"
            if (pointState === 'close' || pointState === 'start-close') {
                this.context.strokeStyle = constants.kTransparentColor
            }else {
                if (type === 'eraser') {
                    this.context.strokeStyle = constants.kLightRedColor
                }else {
                    this.context.strokeStyle = constants.kSkyBlueColor
                }
            }

            if (!isMarking) {
                // this code for default
                this.context.moveTo(points[0].x, points[0].y)
                for (let i = 1; i < points.length - 1; i++) {
                    const xc = (points[i].x + points[i + 1].x) / 2;
                    const yc = (points[i].y + points[i + 1].y) / 2;
                    this.context.quadraticCurveTo(points[i].x, points[i].y, xc, yc);
                    // this.context.quadraticCurveTo(xc, yc, points[i].x, points[i].y);
                }
                this.context.lineTo(points[points.length - 1].x, points[points.length - 1].y);
            } else {
                // this code for marking
                this.context.moveTo(points[0].x / scale, points[0].y / scale)
                for (let i = 1; i < points.length - 1; i++) {
                    const xc = (points[i].x + points[i + 1].x) / 2;
                    const yc = (points[i].y + points[i + 1].y) / 2;
                    this.context.quadraticCurveTo(points[i].x / scale, points[i].y / scale, xc / scale, yc/ scale);
                }
                this.context.lineTo(points[points.length - 1].x / scale, points[points.length - 1].y / scale);
            }
            this.context.stroke()
            this.context.closePath()

            if (pointState === 'close' || pointState === 'start-close') {
                if (type === 'eraser') {
                    this.context.globalCompositeOperation = "destination-out"
                    this.context.fillStyle = constants.kLightRedColor
                }else {
                    this.context.fillStyle = constants.kPrimarySkyBlueColor
                }
                this.context.fill()
                this.getDefaultLineStyle()
            }else {
                this.drawStartPoint(points[0].x, points[0].y, isCloseAble, type, scale)
            }

        }
    }

    // draw paths (pencil, eraser)
    drawPencil(
        points, 
        isCloseAble, 
        type, 
        scale, 
        pointState,
        isMarking = false
    ) {
        if (this.context) {
            if (type === 'eraser') {
                // this.context.lineWidth = constants.kEraserLineWidth / scale
                this.context.lineWidth = constants.kEraserLineWidth * 2
            }else {
                // this.context.lineWidth = constants.kPencilLineWidth / scale
                this.context.lineWidth = constants.kPencilLineWidth * 2
            }
            this.context.lineCap = 'round'
            this.context.lineJoin = 'round'
            this.context.beginPath()
            if (type === 'eraser') {
                this.runPath(points, isCloseAble, type, scale, isMarking, pointState)
            }else {
                this.runPath(points, isCloseAble, 'eraser', scale, isMarking, pointState)
                this.runPath(points, isCloseAble, type, scale, isMarking, pointState)
            }
        }
    }

    // handle when pencil is holding
    holdingPencil(element, scale) {
        if (this.context && element) {
            const { x, y, mouseX, mouseY } = element
            this.context.setLineDash([7])
            this.context.beginPath()
            this.context.moveTo(x / scale, y / scale)
            this.context.lineTo(mouseX / scale, mouseY / scale)
            this.context.stroke()
            this.context.closePath()
            this.context.setLineDash([])
        }
    }

    // translate
    translate(x, y) {
        this.context?.translate(x, y)
    }

    // scale
    scale(scale) {
        this.context?.scale(scale, scale)
    }

    // save casvas state
    save() {
        this.context?.save()
    }

    // restore casvas state
    restore() {
        this.context?.restore()
    }
}