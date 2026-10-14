import Foundation
import Vision
import ImageIO

let url = URL(fileURLWithPath: CommandLine.arguments[1])
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["en-US"]
do {
    try VNImageRequestHandler(url: url, options: [:]).perform([request])
    let observations = (request.results ?? []).sorted {
        if abs($0.boundingBox.midY - $1.boundingBox.midY) > 0.012 {
            return $0.boundingBox.midY > $1.boundingBox.midY
        }
        return $0.boundingBox.minX < $1.boundingBox.minX
    }
    let candidates = observations.compactMap { $0.topCandidates(1).first }
    var words: [[String: Any]] = []
    for candidate in candidates {
        let string = candidate.string
        let regex = try NSRegularExpression(pattern: "\\S+")
        for match in regex.matches(in: string, range: NSRange(string.startIndex..., in: string)) {
            guard let range = Range(match.range, in: string),
                  let observation = try candidate.boundingBox(for: range) else { continue }
            let box = observation.boundingBox
            words.append(["text": String(string[range]), "confidence": Double(candidate.confidence),
                          "box": [Double(box.minX), Double(1 - box.maxY), Double(box.maxX), Double(1 - box.minY)]])
        }
    }
    let output: [String: Any] = [
        "text": candidates.map { $0.string }.joined(separator: "\n"),
        "confidence": candidates.map { Double($0.confidence) }.min() ?? 0,
        "words": words
    ]
    let data = try JSONSerialization.data(withJSONObject: output)
    print(String(data: data, encoding: .utf8)!)
} catch {
    fputs("OCR failed\n", stderr)
    exit(1)
}
