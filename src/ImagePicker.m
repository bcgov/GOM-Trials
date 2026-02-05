#import <Foundation/Foundation.h>
#import "ImagePicker.h"
#import <UIKit/UIKit.h>

static UIImage *ScaleImageToMaxDimension(UIImage *image, CGFloat maxDim) {
    if (!image) return nil;

    CGFloat w = image.size.width;
    CGFloat h = image.size.height;
    CGFloat longEdge = MAX(w, h);

    if (longEdge <= maxDim) {
        return image; // no scaling needed
    }

    CGFloat scale = maxDim / longEdge;
    CGSize newSize = CGSizeMake((CGFloat)round(w * scale), (CGFloat)round(h * scale));

    UIGraphicsBeginImageContextWithOptions(newSize, NO, 1.0); // scale=1 -> pixel dimensions are newSize
    [image drawInRect:CGRectMake(0, 0, newSize.width, newSize.height)];
    UIImage *resized = UIGraphicsGetImageFromCurrentImageContext();
    UIGraphicsEndImageContext();

    return resized;
}

@implementation ImagePicker

- (NSString *)writeToPNG:(NSDictionary *)info {
    UIImage *image = info[UIImagePickerControllerOriginalImage];
    if (!image) {
        NSLog(@"[ImagePicker] No image found in info dictionary.");
        return nil;
    }

    NSData *pngData = UIImagePNGRepresentation(image);
    if (!pngData) {
        NSLog(@"[ImagePicker] Failed to generate PNG data.");
        return nil;
    }

    // Get Documents/images directory
    NSString *docs = [NSSearchPathForDirectoriesInDomains(NSDocumentDirectory,
                                                          NSUserDomainMask,
                                                          YES) firstObject];
    NSString *dir = [docs stringByAppendingPathComponent:@"images"];

    NSError *mkdirErr = nil;
    [[NSFileManager defaultManager] createDirectoryAtPath:dir
                              withIntermediateDirectories:YES
                                               attributes:nil
                                                    error:&mkdirErr];
    if (mkdirErr) {
        NSLog(@"[ImagePicker] Failed to create directory: %@", mkdirErr);
        return nil;
    }

    // Use integer timestamp for filename
    long long ts = (long long)([NSDate timeIntervalSinceReferenceDate] * 1000);
    NSString *fname = [NSString stringWithFormat:@"photo_%lld.png", ts];

    NSString *path = [dir stringByAppendingPathComponent:fname];

    BOOL ok = [pngData writeToFile:path atomically:YES];
    if (!ok) {
        NSLog(@"[ImagePicker] Failed to write PNG to file.");
        return nil;
    }

    return path;
}

- (NSString *)writeToJPG:(NSDictionary *)info quality:(CGFloat)quality maxDim:(CGFloat)maxDim {
    UIImage *image = info[UIImagePickerControllerOriginalImage];
    if (!image) return nil;

    UIImage *scaled = ScaleImageToMaxDimension(image, maxDim);
    if (!scaled) return nil;

    NSData *jpgData = UIImageJPEGRepresentation(scaled, quality);
    if (!jpgData) return nil;

    NSString *docs = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory,
                                                         NSUserDomainMask,
                                                         YES).firstObject;
    NSString *dir = [docs stringByAppendingPathComponent:@"images"];
    [[NSFileManager defaultManager] createDirectoryAtPath:dir
                              withIntermediateDirectories:YES
                                               attributes:nil
                                                    error:nil];

    long long ts = (long long)([NSDate date].timeIntervalSince1970 * 1000);
    NSString *fname = [NSString stringWithFormat:@"photo_%lld.jpg", ts];
    NSString *path = [dir stringByAppendingPathComponent:fname];

    BOOL ok = [jpgData writeToFile:path atomically:YES];
    if (!ok) {
        NSLog(@"[ImagePicker] Failed to write JPEG to file.");
        return nil;
    }
    NSDictionary *attrs = [[NSFileManager defaultManager] attributesOfItemAtPath:path error:nil];
        NSLog(@"[NativeImagePicker] Saved JPEG size on disk: %@ bytes",
              attrs[NSFileSize]);
    
    return path;
}


@end

