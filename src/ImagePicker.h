//
//  NativeImagePicker.h
//  gomapp
//
//  Created by Kiri Daust on 2026-02-02.
//

#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>

@interface ImagePicker : NSObject

// Save a UIImage from the picker "info" dictionary as a PNG.
// Returns the file path (NSString) or nil on failure.
- (NSString *)writeToPNG:(NSDictionary *)info;
- (NSString *)writeToJPG:(NSDictionary *)info quality:(CGFloat)quality maxDim:(CGFloat)maxDim;


@end
